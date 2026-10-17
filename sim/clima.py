"""Fuente de clima simulada (BASE MÍNIMA — Ordenador 2 la sustituye por sim/termico.py).

Modelo de 1 nodo: el aire interior del refugio tiende al exterior según la
ventilación (claraboya), gana calor por sol (cúpula) y por personas, y lo
pierde con el AC y la nebulización. Publica cada `periodo` s reales:
temp, temp_ext, humedad, humedad_ext, radiacion, claraboya, ac, nebulizador, potencia,
solar (placas FV fuera, en la corona de la cúpula), bateria (% carga) y red (W importados).

Energía: las placas cargan la batería; el consumo sale primero del sol, luego de la
batería y, si está vacía (por debajo de BAT_RESERVA), de la red. BAT_RESERVA se
guarda para que la noche no deje sin luz/alerta médica.

Obedece `comando` con destino claraboya (0..1) | ac (bool) | nebulizador (bool):
así el sistema de control se ve funcionar sin hardware.
Escucha `modulos` ({kit,n,area_m2,tipo?,cubierta?}) y reescala en caliente (datos/kits.json).
Escucha `aforo` para sumar 100 W sensibles por persona.
"""
from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path

from nucleo.bus import Bus
from nucleo.evento import Evento
from sim import fisica_pabellon as fp

REFUGIO = "R1"
W_PERSONA = 100.0        # calor sensible por persona sentada (W)
AC_FRIO_W = 3500.0       # potencia frigorífica máx. del AC
AC_COP = 3.0
NEBU_FRIO_W = 1500.0     # enfriamiento evaporativo (cae a 0 con HR alta)
C_AIRE = 1.2 * 1005 * 40  # J/K de ~40 m³ de aire (+mobiliario ligero x3)
C_TOTAL = C_AIRE * 3
UA_CUPULA = 120.0        # W/K conducción por la envolvente
VENT_MAX = 600.0         # W/K extra con la claraboya 100 % abierta (renovación)
G_SOLAR = 0.12         # factor solar efectivo: vidrio de control solar (g≈0.25) × sombra de placas FV y plantas
AREA_SOL = 15.0          # m² de cúpula expuesta al sol directo
AREA_FV = 8.0            # m² de placas FV opacas en la corona (además dan sombra)
EF_FV = 0.20             # eficiencia del panel + inversor
BAT_KWH = 5.0            # batería LiFePO4 del refugio
BAT_RESERVA = 15.0       # % mínimo reservado a control + comunicaciones
CONSIGNA_AC = 25.0       # °C, split inverter del pabellón
MODULOS_BASE = 2         # las constantes de arriba corresponden a 2 módulos
SOMBRA_G = 0.45          # sombra de placas FV y plantas sobre la cubierta
G_POLICARBONATO = 0.30   # g del policarbonato si datos/kits.json lo deja en null
DT_SOMBRA = 3.0          # °C por debajo del exterior a la sombra (espacio abierto)
DT_NEBU_ABIERTO = 1.5    # °C extra con nebulización y aire seco


def _leer_kits() -> dict:
    try:
        d = json.loads((Path(__file__).resolve().parent.parent / "datos" / "kits.json").read_text("utf-8"))
        mod = d["modulo"]
        mats = {}
        for m in d["materiales_cubierta"]:
            g = m.get("g")
            mats[m["id"]] = G_POLICARBONATO if g is None else float(g)
        return {"fv_m2": float(mod["fv_m2"]), "bat_kwh": float(mod["bateria_kwh"]),
                "area_m2": float(mod["area_m2"]), "aforo": int(mod["aforo"]), "materiales": mats}
    except Exception:
        return {"fv_m2": AREA_FV / MODULOS_BASE, "bat_kwh": BAT_KWH / MODULOS_BASE,
                "area_m2": 9.0, "aforo": 10, "materiales": {}}


KITS = _leer_kits()


def _g_cubierta(cubierta: str) -> float | None:
    mats = KITS["materiales"]
    if cubierta in mats:
        return mats[cubierta]
    for k, g in mats.items():
        if k.startswith(cubierta) or cubierta.startswith(k):
            return g
    return None


def t_exterior(h: float) -> float:
    """Ola de calor tipo Barcelona: 26 °C a las 5 h, 36 °C a las 16 h."""
    return 31.0 + 5.0 * math.cos((h - 16.0) / 24.0 * 2 * math.pi)


def hr_exterior(h: float) -> float:
    return 55.0 - 20.0 * math.cos((h - 16.0) / 24.0 * 2 * math.pi)


def radiacion(h: float) -> float:
    return max(0.0, 850.0 * math.sin((h - 6.5) / 14.0 * math.pi)) if 6.5 <= h <= 20.5 else 0.0


class FuenteClimaSim:
    def __init__(self, velocidad: float = 60.0, periodo: float = 1.0,
                 inicio_hora: float = 12.0, refugio: str = REFUGIO,
                 offset_t_ext: float = 0.0, tipo: str = "cupula", n: int = MODULOS_BASE) -> None:
        self.offset_t_ext = offset_t_ext  # °C sumados a t_exterior (escenarios multi-día)
        self.velocidad = velocidad
        self.periodo = periodo
        self.refugio = refugio
        self.t_s = inicio_hora * 3600.0
        self.temp = t_exterior(inicio_hora)
        self.hr = 50.0
        self.claraboya = 0.0
        self.ac = False
        self.nebulizador = False
        self.ventilador = False
        self.aforo = 0
        self.bateria = 60.0     # %
        # parámetros reescalables con el evento `modulos` (por defecto = constantes del módulo)
        self.c_total, self.ua_cupula = C_TOTAL, UA_CUPULA
        self.area_sol, self.area_fv, self.bat_kwh = AREA_SOL, AREA_FV, BAT_KWH
        self.ac_frio_w, self.g_solar = AC_FRIO_W, G_SOLAR
        self.abierto = False
        self.aforo_max = None
        self.tipo = "cupula"
        self.pab: fp.Pabellon | None = None
        self.fisica: dict = {}
        if tipo != "cupula":
            self._modulos({"n": n, "tipo": tipo})

    def _oir(self, ev: Evento) -> None:
        if ev.refugio != self.refugio:
            return
        if ev.tipo == "aforo" and isinstance(ev.valor, (int, float)):
            self.aforo = int(ev.valor)
        elif ev.tipo == "modulos" and isinstance(ev.valor, dict):
            self._modulos(ev.valor)
        elif ev.tipo == "comando" and isinstance(ev.valor, dict):
            d, v = ev.valor.get("destino"), ev.valor.get("valor")
            if d == "claraboya":
                self.claraboya = min(max(float(v), 0.0), 1.0)
            elif d == "ac":
                self.ac = bool(v)
            elif d == "nebulizador":
                self.nebulizador = bool(v)
            elif d == "ventilador":
                self.ventilador = bool(v)

    def _modulos(self, v: dict) -> None:
        """Reescala el refugio a n módulos (y tipo/cubierta) en caliente."""
        try:
            n = max(1, int(v.get("n", MODULOS_BASE)))
        except (TypeError, ValueError):
            return
        f = n / MODULOS_BASE
        self.c_total, self.ua_cupula = C_TOTAL * f, UA_CUPULA * f
        self.area_sol = AREA_SOL * f
        self.area_fv = KITS["fv_m2"] * n
        self.bat_kwh = KITS["bat_kwh"] * n
        self.ac_frio_w = AC_FRIO_W * math.ceil(n / 2)
        self.aforo_max = KITS["aforo"] * n
        self.tipo = str(v.get("tipo", "cupula"))
        self.abierto = self.tipo not in ("cupula", "pabellon")
        if self.tipo == "pabellon":
            # pabellón Venturi: largo 4/6/8 m; capacidad = aire + mobiliario ligero (x3)
            if "largo" in v or "ancho" in v:
                self.pab = fp.pabellon(v.get("largo", 6.0), v.get("ancho", 2.4))
            else:
                self.pab = fp.pabellon_de_modulos(n)
            self.c_total = fp.RHO * fp.CP * self.pab.volumen * 3
            self.ac_frio_w = AC_FRIO_W * math.ceil(self.pab.extractores / 2)
            # placas curvas en el techo: 2 franjas de 1,05 rad sobre r = 1,38 m, 90 % del largo
            self.area_fv = 2 * 1.05 * (self.pab.radio + 0.03) * self.pab.largo * 0.9
            self.bat_kwh = 2.5 * self.pab.largo / 2 * self.pab.ancho / 2.4
            self.aforo_max = int(self.pab.largo * self.pab.ancho / 1.5)   # 1,5 m² por persona
        else:
            self.pab = None
        g = _g_cubierta(str(v["cubierta"])) if v.get("cubierta") else None
        self.g_solar = g * SOMBRA_G if g is not None else G_SOLAR

    def paso(self, dt: float) -> dict:
        """Avanza `dt` s simulados en subpasos de ≤ 30 s (Euler explícito estable)."""
        n = max(1, math.ceil(dt / 30.0))
        for _ in range(n):
            out = self._paso1(dt / n)
        return out

    def _paso_pabellon(self, dt: float, h: float, te: float, hre: float, sol: float) -> tuple[float, float]:
        """Balance del pabellón con ventilación física (sim/fisica_pabellon.py).
        Devuelve (W netos al aire sin AC, W eléctricos extra). La claraboya = garganta Venturi."""
        p = self.pab
        v = fp.viento_barcelona(h)
        # con la garganta cerrada los extractores solo remueven el aire (sensación), no lo renuevan
        f = fp.caudal(p, self.temp, te, v, self.claraboya, self.ventilador and self.claraboya > 0)
        h_vent = fp.RHO * fp.CP * f["caudal"]                       # W/K por renovación de aire
        ua_env = 5.7 * p.area_vidrio * 0.5 + 2.0 * p.area_techo      # vidrio (mitad sombreada por enredaderas) + techo con cámara de aire
        solar = sol * (0.35 * p.area_vidrio / 2 * 0.6 * 0.4 + 0.03 * p.area_techo)   # laterales con enredaderas + techo FV
        q_evap = fp.enfriamiento_evaporativo(p, max(f["caudal"], 0.05), self.temp, self.hr, self.nebulizador)
        q = (ua_env + h_vent) * (te - self.temp) + solar + W_PERSONA * self.aforo - q_evap
        if self.nebulizador:   # el vapor añadido sube la humedad (más cuanto menos se renueva el aire)
            self.hr = min(95.0, self.hr + q_evap / fp.H_FG / (fp.RHO * max(f["caudal"], 0.05)) * 1000 * 4 * dt / 600)
        # la humedad tiende a la exterior al ritmo de las renovaciones
        self.hr += (hre - self.hr) * min(1.0, f["renovaciones_h"] / 3600.0 * dt)
        v_ocu = f["v_ocupante"] + (0.6 if self.ventilador else 0.0)
        self.fisica = {
            "viento": round(v, 2), "dp_venturi": round(f["dp_venturi"], 2), "dp_chimenea": round(f["dp_chimenea"], 3),
            "caudal_m3h": round(f["caudal"] * 3600), "caudal_natural_m3h": round(f["caudal_natural"] * 3600),
            "renovaciones_h": round(f["renovaciones_h"], 1), "v_entrada": round(f["v_entrada"], 2),
            "v_ocupante": round(v_ocu, 2), "evaporativo_w": round(q_evap),
            "t_bulbo_humedo": round(fp.bulbo_humedo(self.temp, self.hr), 1),
            "t_aparente": round(fp.temperatura_aparente(self.temp, self.hr, v_ocu), 1),
            "t_aparente_ext": round(fp.temperatura_aparente(te, hre, v), 1),
            "largo": p.largo, "extractores": p.extractores, "boquillas": p.boquillas}
        extra = (40.0 * p.extractores if self.ventilador else 0.0) + (60.0 if self.nebulizador else 0.0)
        return q, extra

    def _paso1(self, dt: float) -> dict:
        h = (self.t_s / 3600.0) % 24
        te, hre, sol = t_exterior(h) + self.offset_t_ext, hr_exterior(h), radiacion(h)
        if self.pab is not None:
            q, extra = self._paso_pabellon(dt, h, te, hre, sol)
            p_elec = 150.0 + extra
            if self.ac:   # split inverter: modula para llevar el aire a la consigna en ~10 min
                q_ac = min(self.ac_frio_w, max(0.0, q + (self.temp - CONSIGNA_AC) * self.c_total / 600.0))
                q -= q_ac
                p_elec += q_ac / AC_COP
                self.hr = max(45.0, self.hr - 8.0 * dt / 600.0 * q_ac / self.ac_frio_w)
                self.fisica["ac_w"] = round(q_ac)
            self.temp += q * dt / self.c_total
            return self._energia(dt, te, hre, sol, p_elec)
        ua = self.ua_cupula + VENT_MAX * self.claraboya
        q = ua * (te - self.temp) + self.g_solar * self.area_sol * sol + W_PERSONA * self.aforo
        p_elec = 150.0  # control + iluminación + bombas de riego
        if self.ventilador:
            p_elec += 40.0   # mueve aire: no baja la temperatura del aire, sí la sensación (no modelada)
        if self.ac and not self.abierto:
            q -= self.ac_frio_w
            p_elec += self.ac_frio_w / AC_COP
            self.hr = max(45.0, self.hr - 8.0 * dt / 600.0)  # el AC deshumidifica
        if self.nebulizador:
            q -= NEBU_FRIO_W * max(0.0, (80.0 - self.hr) / 50.0)
            self.hr = min(95.0, self.hr + 4.0 * dt / 600.0)
            p_elec += 60.0
        if self.abierto:  # sin envolvente: sombra + nebulización, sin AC
            neb = DT_NEBU_ABIERTO * max(0.0, (80.0 - self.hr) / 50.0) if self.nebulizador else 0.0
            self.temp = te - DT_SOMBRA - neb
        else:
            self.temp += q * dt / self.c_total
        # la humedad tiende a la exterior con la ventilación; personas aportan vapor
        k = (0.2 + 2.0 * self.claraboya) / 3600.0
        self.hr += (hre - self.hr) * min(1.0, k * dt) + 0.02 * self.aforo * dt / 60.0
        self.hr = min(max(self.hr, 15.0), 98.0)
        return self._energia(dt, te, hre, sol, p_elec)

    def _energia(self, dt: float, te: float, hre: float, sol: float, p_elec: float) -> dict:
        self.hr = min(max(self.hr + 0.02 * self.aforo * dt / 60.0 * (self.pab is not None), 15.0), 98.0)
        solar = sol * self.area_fv * EF_FV
        neto_w = solar - p_elec                          # >0 sobra sol, <0 falta
        e_max = self.bat_kwh * 3.6e6
        e_bat = self.bateria / 100.0 * e_max   # J
        e_min = BAT_RESERVA / 100.0 * e_max
        e_nueva = min(max(e_bat + neto_w * dt, min(e_min, e_bat)), e_max)
        red = -(neto_w * dt - (e_nueva - e_bat)) / dt if dt > 0 else 0.0  # + importa, - exporta
        self.bateria = e_nueva / e_max * 100.0
        self.t_s += dt
        out = {"temp": round(self.temp, 2), "temp_ext": round(te, 2), "humedad": round(self.hr, 1),
                "humedad_ext": round(hre, 1), "radiacion": round(sol), "claraboya": self.claraboya,
                "ac": self.ac, "nebulizador": self.nebulizador, "ventilador": self.ventilador, "potencia": round(p_elec),
                "solar": round(solar), "bateria": round(self.bateria, 1), "red": round(red)}
        if self.pab is not None:
            out["viento"] = self.fisica["viento"]
            out["fisica"] = self.fisica
        return out

    async def correr(self, bus: Bus) -> None:
        baja = bus.oyente(self._oir)
        try:
            while True:
                for tipo, valor in self.paso(self.periodo * self.velocidad).items():
                    bus.publicar(Evento(tipo, valor, "sim", self.refugio))
                await asyncio.sleep(self.periodo)
        finally:
            baja()
