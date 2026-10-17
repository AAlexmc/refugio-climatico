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
Escucha `aforo` para sumar 100 W sensibles por persona.
"""
from __future__ import annotations

import asyncio
import math

from nucleo.bus import Bus
from nucleo.evento import Evento

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
                 offset_t_ext: float = 0.0) -> None:
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

    def _oir(self, ev: Evento) -> None:
        if ev.refugio != self.refugio:
            return
        if ev.tipo == "aforo" and isinstance(ev.valor, (int, float)):
            self.aforo = int(ev.valor)
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

    def paso(self, dt: float) -> dict:
        """Avanza `dt` s simulados en subpasos de ≤ 30 s (Euler explícito estable)."""
        n = max(1, math.ceil(dt / 30.0))
        for _ in range(n):
            out = self._paso1(dt / n)
        return out

    def _paso1(self, dt: float) -> dict:
        h = (self.t_s / 3600.0) % 24
        te, hre, sol = t_exterior(h) + self.offset_t_ext, hr_exterior(h), radiacion(h)
        ua = UA_CUPULA + VENT_MAX * self.claraboya
        q = ua * (te - self.temp) + G_SOLAR * AREA_SOL * sol + W_PERSONA * self.aforo
        p_elec = 150.0  # control + iluminación + bombas de riego
        if self.ventilador:
            p_elec += 40.0   # mueve aire: no baja la temperatura del aire, sí la sensación (no modelada)
        if self.ac:
            q -= AC_FRIO_W
            p_elec += AC_FRIO_W / AC_COP
            self.hr = max(45.0, self.hr - 8.0 * dt / 600.0)  # el AC deshumidifica
        if self.nebulizador:
            q -= NEBU_FRIO_W * max(0.0, (80.0 - self.hr) / 50.0)
            self.hr = min(95.0, self.hr + 4.0 * dt / 600.0)
            p_elec += 60.0
        self.temp += q * dt / C_TOTAL
        solar = sol * AREA_FV * EF_FV
        neto_w = solar - p_elec                          # >0 sobra sol, <0 falta
        e_bat = self.bateria / 100.0 * BAT_KWH * 3.6e6   # J
        e_min = BAT_RESERVA / 100.0 * BAT_KWH * 3.6e6
        e_max = BAT_KWH * 3.6e6
        e_nueva = min(max(e_bat + neto_w * dt, min(e_min, e_bat)), e_max)
        red = -(neto_w * dt - (e_nueva - e_bat)) / dt if dt > 0 else 0.0  # + importa, - exporta
        self.bateria = e_nueva / (BAT_KWH * 3.6e6) * 100.0
        # la humedad tiende a la exterior con la ventilación; personas aportan vapor
        k = (0.2 + 2.0 * self.claraboya) / 3600.0
        self.hr += (hre - self.hr) * min(1.0, k * dt) + 0.02 * self.aforo * dt / 60.0
        self.hr = min(max(self.hr, 15.0), 98.0)
        self.t_s += dt
        return {"temp": round(self.temp, 2), "temp_ext": round(te, 2), "humedad": round(self.hr, 1),
                "humedad_ext": round(hre, 1), "radiacion": round(sol), "claraboya": self.claraboya,
                "ac": self.ac, "nebulizador": self.nebulizador, "ventilador": self.ventilador, "potencia": round(p_elec),
                "solar": round(solar), "bateria": round(self.bateria, 1), "red": round(red)}

    async def correr(self, bus: Bus) -> None:
        baja = bus.oyente(self._oir)
        try:
            while True:
                for tipo, valor in self.paso(self.periodo * self.velocidad).items():
                    bus.publicar(Evento(tipo, valor, "sim", self.refugio))
                await asyncio.sleep(self.periodo)
        finally:
            baja()
