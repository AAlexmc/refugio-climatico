"""Métricas del escenario de 5 días de ola de calor: calle / cúpula sin control / OASI.

Reutiliza la física de `sim/clima.py` y las reglas de `control/reglas.py` en lazo
cerrado sobre un Bus en memoria (síncrono, sin asyncio). Determinista.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from control.reglas import MotorReglas
from nucleo.bus import Bus
from nucleo.confort import indice_calor
from nucleo.evento import Evento
from sim import clima

DIAS = 5
PASO_S = 600.0      # muestreo de las series
CTRL_S = 30.0       # paso de control/física (el AC de 3,5 kW oscila si se controla a 600 s)
OFFSET_DIA = (0.0, 0.5, 1.0, 1.5, 2.0)   # °C extra sobre la ola de calor base
UMBRAL_RIESGO = 32.0
EUR_KWH = 0.20
KG_CO2_KWH = 0.2


def aforo_en(h: float, cap: int = 20) -> int:
    """Ocupación según la capacidad `cap`: casi vacío de noche (1-2), 30 % por la mañana y al
    anochecer, 75 % de 10 a 19 h y lleno en la primera media hora de las horas pares (autobús)."""
    if 10 <= h < 19:
        return cap if (int(h) % 2 == 0 and h % 1 < 0.5) else round(0.75 * cap)
    if 7 <= h < 10 or 19 <= h < 23:
        return max(1, round(0.3 * cap))
    return min(2, cap)


def _r(x: float, n: int = 1) -> float:
    return round(float(x), n)


def _simular(dias: int = DIAS, cubierta: str | None = None, modulos: int | None = None,
             largo: float | None = None, ancho: float | None = None) -> dict:
    bus = Bus()
    m = MotorReglas(bus, avisar=lambda r, msg: None)
    bus.oyente(m.procesar)
    # escenario principal = Pabellón Venturi (6 m) con física de ventilación; los extras por
    # cubierta/módulos siguen usando el modelo de cúpula para comparar materiales
    tipo = "pabellon" if cubierta is None and modulos is None else "cupula"
    oasi = clima.FuenteClimaSim(inicio_hora=0.0, tipo=tipo)
    bus.oyente(oasi._oir)
    cup = clima.FuenteClimaSim(inicio_hora=0.0, tipo=tipo)
    if tipo == "pabellon" and (largo or ancho):
        for f in (oasi, cup):
            f._modulos({"tipo": "pabellon", "largo": largo or 6.0, "ancho": ancho or 2.4})
    if cubierta is not None or modulos is not None:
        ev = {"n": modulos or clima.MODULOS_BASE}
        if cubierta:
            ev["cubierta"] = cubierta
        for f in (oasi, cup):
            f._modulos(ev)   # sin reglas: claraboya cerrada, nada encendido
    ref = oasi.refugio
    t, calle, t_oasi, t_cup, solar, cons, bat, afo = ([] for _ in range(8))
    at_oasi, at_calle, caudal, viento = ([] for _ in range(4))
    n_sub = round(PASO_S / CTRL_S)
    kwh_sol = kwh_cons = kwh_red = 0.0           # J -> kWh al final
    ries_calle = ries_oasi = 0                   # subpasos con índice de calor > umbral
    noche_w = noche_n = 0
    pico = 0.0
    for i in range(int(dias * 86400 / PASO_S)):
        sol_m = cons_m = 0.0
        for j in range(n_sub):
            seg = i * PASO_S + j * CTRL_S
            h = (seg / 3600.0) % 24
            oasi.offset_t_ext = cup.offset_t_ext = OFFSET_DIA[min(int(seg // 86400), len(OFFSET_DIA) - 1)]
            a = aforo_en(h, oasi.aforo_max or 20)
            cup.aforo = a
            bus.publicar(Evento("aforo", a, "sim", ref))   # oasi lo recibe por el bus
            d = oasi.paso(CTRL_S)
            c = cup.paso(CTRL_S)
            for tipo in ("temp_ext", "temp", "humedad"):
                bus.publicar(Evento(tipo, d[tipo], "sim", ref))
            sol_m += d["solar"] / n_sub
            cons_m += d["potencia"] / n_sub
            kwh_sol += d["solar"] * CTRL_S
            kwh_cons += d["potencia"] * CTRL_S
            kwh_red += max(0.0, d["red"]) * CTRL_S
            ries_calle += indice_calor(d["temp_ext"], d["humedad_ext"]) > UMBRAL_RIESGO
            ries_oasi += indice_calor(d["temp"], d["humedad"]) > UMBRAL_RIESGO
            if d["radiacion"] > 0:
                pico = max(pico, d["temp_ext"] - d["temp"])
            else:
                noche_w += d["potencia"]
                noche_n += 1
        t.append(int((i + 1) * PASO_S))
        calle.append(d["temp_ext"])
        t_oasi.append(d["temp"])
        t_cup.append(c["temp"])
        solar.append(sol_m)
        cons.append(cons_m)
        bat.append(d["bateria"])
        afo.append(a)
        fz = oasi.fisica
        if fz:
            at_oasi.append(fz["t_aparente"]); at_calle.append(fz["t_aparente_ext"])
            caudal.append(fz["caudal_m3h"]); viento.append(fz["viento"])
    kwh_sol, kwh_cons, kwh_red = (x / 3.6e6 for x in (kwh_sol, kwh_cons, kwh_red))
    cons_noche = noche_w / noche_n if noche_n else kwh_cons * 1000.0 / (dias * 24)
    usable_kwh = oasi.bat_kwh * (100.0 - clima.BAT_RESERVA) / 100.0
    h_sub = CTRL_S / 3600.0
    ries_calle *= h_sub
    ries_oasi *= h_sub
    res = {
        "series": {"t": t, "temp_calle": [_r(x, 2) for x in calle], "temp_oasi": [_r(x, 2) for x in t_oasi],
                   "temp_cupula": [_r(x, 2) for x in t_cup], "solar": [int(x) for x in solar],
                   "consumo": [int(x) for x in cons], "bateria": [_r(x) for x in bat], "aforo": afo,
                   **({"t_aparente_oasi": at_oasi, "t_aparente_calle": at_calle, "caudal_m3h": caudal, "viento": viento}
                      if at_oasi else {})},
        "resumen": {
            "grados_reducidos_pico": _r(pico),
            "horas_riesgo_evitadas": _r(ries_calle - ries_oasi),
            "kwh_solares": _r(kwh_sol),
            "pct_autoconsumo": _r(100.0 * (1.0 - kwh_red / kwh_cons) if kwh_cons else 0.0),
            "autonomia_h": _r(usable_kwh * 1000.0 / cons_noche if cons_noche else 0.0),
            "coste_eur_dia": _r(kwh_red / dias * EUR_KWH, 2),
            "co2_kg_evitado": _r(kwh_sol * KG_CO2_KWH, 2),
        },
    }
    if dias == DIAS and cubierta is None and modulos is None:   # escenario principal: añade los extras
        res["resumen"].update(_extras())
    return res


DIAS_EXTRA = 2


def _extras() -> dict:
    """Temp. máx. OASI por cubierta (+ vidrio simple) y energía/autonomía por kit."""
    ids = list(clima.KITS["materiales"]) or []
    mats = {}
    for mid in ids:
        r = _simular(DIAS_EXTRA, cubierta=mid)
        mats[mid] = _r(max(r["series"]["temp_oasi"]), 2)
    kits = {}
    try:
        lista = json.loads((Path(clima.__file__).resolve().parent.parent / "datos" / "kits.json").read_text("utf-8"))["kits"]
    except Exception:
        lista = []
    for k in lista:
        if k.get("tipo", "cupula") != "cupula":
            continue
        r = _simular(DIAS_EXTRA, modulos=int(k["modulos"]))["resumen"]
        kits[k["id"]] = {"kwh_solares_dia": _r(r["kwh_solares"] / DIAS_EXTRA, 2), "autonomia_h": r["autonomia_h"]}
    return {"materiales": mats, "kits": kits}


@lru_cache(maxsize=1)
def escenario() -> dict:
    return _simular()


@lru_cache(maxsize=16)
def dia(largo: float = 6.0, ancho: float = 2.4) -> dict:
    """Un día de ola de calor para un pabellón de largo x ancho (panel inferior del gemelo)."""
    from sim import fisica_pabellon as fp
    p = fp.pabellon(largo, ancho)
    r = _simular(1, largo=p.largo, ancho=p.ancho)
    r["pabellon"] = {"largo": p.largo, "ancho": p.ancho, "volumen_m3": round(p.volumen, 1),
                     "aforo_max": int(p.largo * p.ancho / 1.5), "extractores": p.extractores, "boquillas": p.boquillas}
    return r
