"""Control del refugio (BASE — Ordenador 2 la mejora): medidas -> comandos + alertas.

`MotorReglas(bus)` es un oyente síncrono (`bus.oyente(motor.procesar)`).
Solo publica en CAMBIOS (comando nuevo o cambio de nivel de alerta).

Reglas base, en orden de prioridad:
1. Desmayo / caída  -> alerta crítica "desmayo" + aviso a servicio médico (control/alerta_medica.py).
2. Lluvia            -> claraboya cerrada.
3. Ventilación natural primero: si fuera está ≥ 1 °C más fresco que dentro Y fuera < 27 °C
   -> claraboya abierta, AC apagado (con 35 °C fuera abrir solo mete calor).
4. Índice de calor interior > 27 °C con claraboya cerrada -> AC encendido (histéresis 1 °C).
5. AFLUENCIA: con ≥ AFORO_ACTIVAR (4) personas detectadas se refuerza el sistema térmico:
   ventilador on, AC on con consigna más baja (IC > 25 °C, aunque se pueda ventilar: la
   claraboya sigue abierta si fuera está fresco) y nebulizador si el aire es seco.
   Aviso "afluencia" en el panel/gemelo. Por debajo de 4, vuelven las reglas normales.
5b. Nebulizador SOLO si HR < 60 % (con humedad alta el
   evaporativo sube el índice de calor: empeora el confort).
6. Aforo > máximo -> aviso "lleno" (la app ciudadana redirige al refugio más cercano).
"""
from __future__ import annotations

import time
from collections.abc import Callable

from control import alerta_medica
from nucleo.bus import Bus
from nucleo.confort import indice_calor
from nucleo.evento import Evento, alerta

IC_AC_ON = 27.0
HISTERESIS = 1.0
DELTA_VENT = 1.0
AFORO_MAX = 20
AFORO_ACTIVAR = 4         # personas: a partir de aquí se refuerza el sistema térmico
IC_AC_AFLUENCIA = 25.0
MANTENER_AFLUENCIA_S = 30.0  # s reales: el conteo de la cámara parpadea; no encender/apagar cada frame
HR_MAX_NEBU = 60.0
T_MIN_NEBU = 26.0

ENTRADAS = {"temp", "temp_ext", "humedad", "aforo", "lluvia", "caida", "desmayo"}


class MotorReglas:
    def __init__(self, bus: Bus, *, aforo_max: int = AFORO_MAX, reloj: Callable[[], float] = time.monotonic,
                 avisar: Callable[[str, str], None] = alerta_medica.avisar) -> None:
        self.bus = bus
        self.aforo_max = aforo_max
        self.avisar = avisar
        self.reloj = reloj
        self._afluencia_hasta: dict[str, float] = {}
        self.v: dict[str, dict] = {}            # refugio -> {tipo: valor}
        self.cmd: dict[tuple[str, str], object] = {}
        self.alertas: dict[tuple[str, str], str] = {}

    def _comando(self, r: str, destino: str, valor) -> None:
        if self.cmd.get((r, destino)) == valor:
            return
        self.cmd[(r, destino)] = valor
        self.bus.publicar(Evento("comando", {"destino": destino, "valor": valor}, "reglas", r))

    def _alerta(self, r: str, codigo: str, nivel: str, mensaje: str) -> None:
        if self.alertas.get((r, codigo), "info") == nivel:
            return
        self.alertas[(r, codigo)] = nivel
        self.bus.publicar(alerta(nivel, codigo, mensaje, refugio=r))

    def procesar(self, ev: Evento) -> None:
        if ev.tipo not in ENTRADAS:
            return
        r = ev.refugio
        v = self.v.setdefault(r, {})
        v[ev.tipo] = ev.valor
        self._emergencia(r, v)
        self._clima(r, v)

    def _emergencia(self, r: str, v: dict) -> None:
        d = v.get("desmayo")
        activo = (isinstance(d, dict) and d.get("activo")) or v.get("caida") is True
        if activo:
            if self.alertas.get((r, "desmayo")) != "critico":
                self.avisar(r, "Persona en el suelo sin moverse en el refugio")
            self._alerta(r, "desmayo", "critico", "Persona en el suelo: aviso enviado al 061 (SEM)")
        else:
            self._alerta(r, "desmayo", "info", "Sin incidencias médicas")

    def _clima(self, r: str, v: dict) -> None:
        if "temp" not in v or "humedad" not in v:
            return
        t, hr = float(v["temp"]), float(v["humedad"])
        ic = indice_calor(t, hr)
        te = v.get("temp_ext")
        aforo = int(v.get("aforo", 0) or 0)
        lluvia = v.get("lluvia") is True

        ventilar = (not lluvia) and te is not None and float(te) <= t - DELTA_VENT and float(te) < IC_AC_ON
        self._comando(r, "claraboya", 1.0 if ventilar else 0.0)

        ahora = self.reloj()
        if aforo >= AFORO_ACTIVAR:
            self._afluencia_hasta[r] = ahora + MANTENER_AFLUENCIA_S
        afluencia = ahora < self._afluencia_hasta.get(r, float("-inf"))
        ac_prev = bool(self.cmd.get((r, "ac"), False))
        umbral = IC_AC_AFLUENCIA if afluencia else IC_AC_ON
        if ventilar and not afluencia:
            ac = False
        elif ac_prev:
            ac = ic > umbral - HISTERESIS
        else:
            ac = ic > umbral
        self._comando(r, "ac", ac)
        self._comando(r, "ventilador", afluencia)
        self._comando(r, "nebulizador", bool(afluencia and t >= T_MIN_NEBU and hr < HR_MAX_NEBU))
        if afluencia:
            self._alerta(r, "afluencia", "aviso",
                         f"{aforo} personas: refuerzo térmico activo (ventilador + AC"
                         + (" + nebulizador)" if hr < HR_MAX_NEBU and t >= T_MIN_NEBU else ")"))
        else:
            self._alerta(r, "afluencia", "info", f"{aforo} personas: modo normal")

        if aforo > self.aforo_max:
            self._alerta(r, "lleno", "aviso", f"Refugio lleno ({aforo}/{self.aforo_max})")
        else:
            self._alerta(r, "lleno", "info", f"Aforo {aforo}/{self.aforo_max}")
