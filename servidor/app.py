"""Servidor del panel: bus + fuentes + reglas + WebSocket + estáticos.

    python -m servidor.app                        # todo simulado
    python -m servidor.app --clima esp32 --pose realsense

Rutas:
    GET  /               panel (web/index.html)
    GET  /api/estado     último valor por (refugio, tipo)
    POST /api/evento     inyectar un evento (ESP32 por WiFi, pruebas, demo)
    POST /api/comando    {"destino": "rele", "valor": true} -> actuadores
    GET/POST /api/pose/modo         {"modo": "camara" | "sim"} quién alimenta al refugio
    GET  /api/caida/vivo            cadera_z, ángulo, estado del detector (cámara)
    POST /api/caida/grabar          {"clase": "de_pie" | "suelo", "segundos": 3} -> medianas
    POST /api/caida/calcular        {"pie": {...}, "suelo": {...}} -> umbrales (sin guardar)
    GET/POST/DELETE /api/caida/calibracion   leer / guardar+aplicar en caliente / defaults
    WS   /ws             flujo de eventos JSON (primero el estado actual)
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import importlib
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dataclasses import asdict

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles


class _Estaticos(StaticFiles):
    """Ficheros del panel con `no-cache`: el navegador revalida (ETag -> 304) y nunca
    se queda con un panel.js/twin*.js anterior a un cambio."""

    def file_response(self, *args, **kwargs):
        r = super().file_response(*args, **kwargs)
        r.headers["Cache-Control"] = "no-cache"
        return r

from vision import calibracion
from vision.caidas import Umbrales
from vision.modo_pose import Conmutador
from nucleo import fuente as fuentes
from nucleo.bus import Bus
from nucleo.evento import Evento

STATIC = Path(__file__).resolve().parent.parent / "web"


def _motor_reglas(bus: Bus):
    """Engancha control.reglas si existe. Sin reglas el panel sigue
    mostrando medidas; solo faltan alertas calculadas."""
    try:
        mod = importlib.import_module("control.reglas")
    except ModuleNotFoundError:
        return None
    motor = mod.MotorReglas(bus)
    bus.oyente(motor.procesar)
    return motor


def crear_app(nombres: list[tuple[str, dict]] | None = None, *, bus: Bus | None = None,
              modo_inicial: str = "camara") -> FastAPI:
    bus = bus or Bus()
    nombres = nombres or []

    @asynccontextmanager
    async def vida(app: FastAPI):
        bus.enlazar_loop(asyncio.get_running_loop())
        app.state.reglas = _motor_reglas(bus)
        objs = {n: fuentes.crear(n, **kw) for n, kw in nombres}
        app.state.fuentes = objs
        cam = next((objs[n] for n in ("realsense", "webcam") if n in objs), None)
        sim = objs.get("pose_sim")
        app.state.camara = cam
        app.state.modo = None
        tareas = []
        if cam is not None and sim is not None:   # ambas: conmutador cámara/simulación
            app.state.modo = modo = Conmutador(bus, cam, sim, pedido=modo_inicial)
            tareas = [asyncio.create_task(cam.correr(modo.proxy("camara")), name="camara"),
                      asyncio.create_task(sim.correr(modo.proxy("sim")), name="pose_sim"),
                      asyncio.create_task(modo.vigilar(), name="modo_pose")]
        tareas += [asyncio.create_task(f.correr(bus), name=n) for n, f in objs.items()
                   if app.state.modo is None or f not in (cam, sim)]
        try:
            yield
        finally:
            for t in tareas:
                t.cancel()
            for t in tareas:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await t

    app = FastAPI(title="OASI refugio climático", lifespan=vida)
    app.state.bus = bus

    @app.get("/api/estado")
    async def estado():
        return bus.estado()

    @app.post("/api/evento")
    async def evento(d: dict = Body(...)):
        try:
            ev = Evento.from_dict(d)
        except (KeyError, ValueError, TypeError) as e:
            raise HTTPException(422, str(e))
        bus.publicar(ev)
        return {"ok": True}

    @app.post("/api/comando")
    async def comando(d: dict = Body(...)):
        if "destino" not in d or "valor" not in d:
            raise HTTPException(422, "faltan destino/valor")
        bus.publicar(Evento("comando", {"destino": d["destino"], "valor": d["valor"]},
                            "panel", d.get("refugio", "R1")))
        return {"ok": True}

    # -- modo cámara / simulación -------------------------------------
    @app.get("/api/pose/modo")
    async def modo_get():
        if app.state.modo is not None:
            return app.state.modo.estado()
        m = "camara" if app.state.camara is not None else (
            "sim" if "pose_sim" in app.state.fuentes else "ninguno")
        return {"modo": m, "pedido": m, "auto": False, "camara_ok": app.state.camara is not None,
                "conmutable": False}

    @app.post("/api/pose/modo")
    async def modo_post(d: dict = Body(...)):
        if app.state.modo is None:
            raise HTTPException(409, "no hay cámara y simulación a la vez (--pose realsense|webcam)")
        try:
            return app.state.modo.pedir(d.get("modo"))
        except ValueError as e:
            raise HTTPException(422, str(e))

    # -- entrenamiento de caída ---------------------------------------
    def _cam():
        cam = app.state.camara
        if cam is None:
            raise HTTPException(409, "sin cámara: arranca con --pose realsense|webcam")
        return cam

    @app.get("/api/caida/vivo")
    async def caida_vivo():
        from vision.vista import VISTA
        cam = _cam()
        v = cam.vivo
        return {**v, "edad_s": None if v["t"] is None else max(0.0, time.time() - v["t"]),
                "vista": VISTA.activa, "umbrales": asdict(cam.umbrales),
                "grabando": cam._grabador.activo}

    @app.post("/api/caida/grabar")
    async def caida_grabar(d: dict = Body(...)):
        cam = _cam()
        if d.get("clase") not in ("de_pie", "suelo"):
            raise HTTPException(422, "clase: de_pie | suelo")
        try:
            seg = min(max(float(d.get("segundos", 3)), 0.2), 10.0)
            muestras = await cam.grabar(seg)
        except RuntimeError as e:
            raise HTTPException(409, str(e))
        except (TypeError, ValueError) as e:
            raise HTTPException(422, str(e))
        try:
            return {"clase": d["clase"], **calibracion.mediana(muestras)}
        except calibracion.ErrorCalibracion as e:
            raise HTTPException(422, str(e))

    @app.post("/api/caida/calcular")
    async def caida_calcular(d: dict = Body(...)):
        try:
            exigir = d.get("exigir_descenso", True)
            if not isinstance(exigir, bool):
                raise calibracion.ErrorCalibracion("exigir_descenso debe ser true o false")
            u, nota = calibracion.calcular(d.get("pie"), d.get("suelo"), exigir_descenso=exigir)
            u = calibracion.validar(asdict(u))
        except calibracion.ErrorCalibracion as e:
            raise HTTPException(422, str(e))
        return {"umbrales": asdict(u), "nota": nota}

    @app.get("/api/caida/calibracion")
    async def caida_cal_get():
        cam = app.state.camara
        guardada = calibracion.cargar(cam.calibracion_ruta if cam else calibracion.RUTA)
        return {"umbrales": asdict(cam.umbrales if cam else guardada or Umbrales()),
                "defaults": asdict(Umbrales()), "guardada": guardada is not None}

    @app.post("/api/caida/calibracion")
    async def caida_cal_post(d: dict = Body(...)):
        cam = _cam()
        try:
            u = calibracion.validar(d)
        except calibracion.ErrorCalibracion as e:
            raise HTTPException(422, str(e))
        try:
            calibracion.guardar(u, cam.calibracion_ruta)
        except OSError as e:
            raise HTTPException(500, f"no se pudo guardar: {e}")
        cam.aplicar_umbrales(u)
        return {"ok": True, "umbrales": asdict(u)}

    @app.delete("/api/caida/calibracion")
    async def caida_cal_delete():
        cam = _cam()
        calibracion.borrar(cam.calibracion_ruta)
        cam.aplicar_umbrales(Umbrales())
        return {"ok": True, "umbrales": asdict(Umbrales())}

    @app.get("/camara.mjpg")
    async def camara():
        from vision.vista import VISTA
        if not VISTA.activa:
            raise HTTPException(404, "arranca con --ver-camara (y --pose realsense|webcam)")

        async def flujo():
            visto = 0
            while True:
                visto, jpg = await asyncio.to_thread(VISTA.esperar, visto)
                if jpg:
                    yield b"--f\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
        return StreamingResponse(flujo(), media_type="multipart/x-mixed-replace; boundary=f")

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        await sock.accept()
        try:
            for d in bus.estado():
                await sock.send_json(d)
            async for ev in bus.suscribir():
                await sock.send_json(ev.to_dict())
        except (WebSocketDisconnect, RuntimeError):
            pass

    if STATIC.is_dir():
        app.mount("/", _Estaticos(directory=STATIC, html=True), name="static")
    return app


def _args(argv=None):
    p = argparse.ArgumentParser(description="OASI refugio climático — servidor del panel")
    p.add_argument("--clima", choices=["sim", "esp32", "off"], default="sim",
                   help="temp/humedad/luz/red: simulador o ESP32 real")
    p.add_argument("--aforo", choices=["aforo_sim", "yolo", "off"], default="aforo_sim",
                   help="conteo de personas: simulado o cámara (vision/aforo.py)")
    p.add_argument("--puerto", default="/dev/ttyACM0", help="puerto serie del ESP32")
    p.add_argument("--pose", choices=["pose_sim", "realsense", "webcam", "off"], default="pose_sim")
    p.add_argument("--modo-inicial", choices=["camara", "sim"], default="camara",
                   help="con --pose realsense|webcam: quién alimenta al refugio al arrancar")
    p.add_argument("--velocidad", type=float, default=60.0,
                   help="segundos simulados por segundo real (sim)")
    p.add_argument("--ver-camara", action="store_true",
                   help="depuración: /camara.html muestra la imagen con el esqueleto (no se guarda)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    return p.parse_args(argv)


def main(argv=None) -> None:
    import uvicorn

    a = _args(argv)
    nombres: list[tuple[str, dict]] = []
    if a.clima == "sim":
        nombres.append(("sim", {"velocidad": a.velocidad}))
    if a.aforo != "off":
        nombres.append((a.aforo, {}))
    elif a.clima == "esp32":
        nombres.append(("esp32", {"puerto": a.puerto}))
    if a.pose in ("realsense", "webcam"):
        nombres.append((a.pose, {"camara": a.pose, "ver": a.ver_camara}))
        nombres.append(("pose_sim", {}))   # respaldo / modo sin visión (conmutador)
        if a.ver_camara:
            from vision.vista import VISTA
            VISTA.activa = True
    elif a.pose == "pose_sim":
        nombres.append(("pose_sim", {}))
    uvicorn.run(crear_app(nombres, modo_inicial=a.modo_inicial), host=a.host, port=a.port, log_level="info",
                timeout_graceful_shutdown=2)  # un /camara.mjpg abierto no bloquea el cierre


if __name__ == "__main__":
    main()
