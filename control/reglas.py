"""Control del refugio (BASE — Ordenador 2 la mejora): medidas -> comandos + alertas.

`MotorReglas(bus)` es un oyente síncrono (`bus.oyente(motor.procesar)`).
Solo publica en CAMBIOS (comando nuevo o cambio de nivel de alerta).

Reglas base, en orden de prioridad:
1. Caída sola       -> aviso "caida" (Persona en el suelo). SOLO `desmayo.activo` -> alerta crítica
   "desmayo" + aviso al 061 (control/alerta_medica.py) con persona y aforo. El panel puede marcar
   «Atendido» (comando destino=atendido, valor=desmayo): pasa a aviso hasta que el desmayo se reinicie.
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
7. Publica `indice_calor`; alerta "calor" (IC > 32 aviso, ≤ 31 info); "bateria_baja" (< 20 % ahorro:
   consigna AC +2 °C, ≥ 25 % normal); CO₂ > 1000 ppm -> claraboya ≥ 0.6 + aviso "co2";
   claraboya parcial (0.6 si fuera está 1-3 °C más fresco, 1.0 si ≥ 3 °C); ahorro solar
   (solar > 0.8·potencia y batería > 90 % -> preenfría, consigna AC -1 °C).
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
IC_CALOR_ON = 32.0
IC_CALOR_OFF = 31.0
BATERIA_BAJA = 20.0
BATERIA_OK = 25.0
DELTA_AHORRO = 2.0
CO2_MAX = 1000.0
CLARABOYA_CO2 = 0.6
DELTA_PARCIAL = 3.0
PREENFRIAR_BATERIA = 90.0
PREENFRIAR_SOLAR = 0.8
DELTA_PREENFRIAR = 1.0

ENTRADAS = {"temp", "temp_ext", "humedad", "aforo", "lluvia", "caida", "desmayo",
            "co2", "bateria", "solar", "potencia", "comando"}


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
        self._atendido: set[str] = set()
        self._ic: dict[str, float] = {}
        self._ahorro: dict[str, bool] = {}

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
        if ev.tipo == "comando":
            self._atender(r, ev)
            return
        v = self.v.setdefault(r, {})
        v[ev.tipo] = ev.valor
        self._emergencia(r, v)
        self._clima(r, v)

    def _atender(self, r: str, ev: Evento) -> None:
        """«Atendido» del panel; ignora los comandos que publica el propio motor."""
        c = ev.valor
        if ev.fuente == "reglas" or not isinstance(c, dict):
            return
        if c.get("destino") != "atendido" or c.get("valor") != "desmayo":
            return
        d = self.v.get(r, {}).get("desmayo")
        if isinstance(d, dict) and d.get("activo"):
            self._atendido.add(r)
            self._emergencia(r, self.v[r])

    def _emergencia(self, r: str, v: dict) -> None:
        d = v.get("desmayo")
        desmayo = isinstance(d, dict) and bool(d.get("activo"))
        if v.get("caida") is True:
            self._alerta(r, "caida", "aviso", "Persona en el suelo")
        else:
            self._alerta(r, "caida", "info", "Sin caídas")
        if desmayo and r in self._atendido:
            self._alerta(r, "desmayo", "aviso", "Atendido por el equipo médico")
        elif desmayo:
            if self.alertas.get((r, "desmayo")) != "critico":
                persona = d.get("persona")
                quien = f" (persona {persona})" if persona not in (None, "") else ""
                self.avisar(r, f"Persona desmayada{quien} en el refugio; aforo actual: {int(v.get('aforo', 0) or 0)}")
            self._alerta(r, "desmayo", "critico", "Persona desmayada: aviso enviado al 061 (SEM)")
        else:
            self._atendido.discard(r)
            self._alerta(r, "desmayo", "info", "Sin incidencias médicas")

    def _clima(self, r: str, v: dict) -> None:
        if "temp" not in v or "humedad" not in v:
            return
        t, hr = float(v["temp"]), float(v["humedad"])
        ic = indice_calor(t, hr)
        ic_r = round(ic, 1)
        if self._ic.get(r) != ic_r:
            self._ic[r] = ic_r
            self.bus.publicar(Evento("indice_calor", ic_r, "reglas", r))
        if ic > IC_CALOR_ON:
            self._alerta(r, "calor", "aviso", f"Índice de calor interior {ic_r} °C")
        elif ic <= IC_CALOR_OFF:
            self._alerta(r, "calor", "info", f"Índice de calor interior {ic_r} °C")

        bat = v.get("bateria")
        if bat is not None:
            if float(bat) < BATERIA_BAJA:
                self._ahorro[r] = True
            elif float(bat) >= BATERIA_OK:
                self._ahorro[r] = False
        ahorro = self._ahorro.get(r, False)
        if ahorro:
            self._alerta(r, "bateria_baja", "aviso", f"Batería {float(bat):.0f} %: modo ahorro (AC +{DELTA_AHORRO:g} °C)")
        elif bat is not None and float(bat) >= BATERIA_OK:
            self._alerta(r, "bateria_baja", "info", f"Batería {float(bat):.0f} %")
        solar, pot = v.get("solar"), v.get("potencia")
        preenfriar = (not ahorro and bat is not None and float(bat) > PREENFRIAR_BATERIA
                      and solar is not None and pot is not None and float(solar) > PREENFRIAR_SOLAR * float(pot))
        co2 = v.get("co2")
        co2_alto = co2 is not None and float(co2) > CO2_MAX
        if co2 is not None:
            if co2_alto:
                self._alerta(r, "co2", "aviso", f"CO₂ {float(co2):.0f} ppm: renovando aire")
            else:
                self._alerta(r, "co2", "info", f"CO₂ {float(co2):.0f} ppm")
        te = v.get("temp_ext")
        aforo = int(v.get("aforo", 0) or 0)
        lluvia = v.get("lluvia") is True

        ventilar = (not lluvia) and te is not None and float(te) <= t - DELTA_VENT and float(te) < IC_AC_ON
        if not ventilar:
            claraboya = 0.0
        elif float(te) <= t - DELTA_PARCIAL:
            claraboya = 1.0
        else:
            claraboya = 0.6
        if co2_alto and not lluvia:
            claraboya = max(claraboya, CLARABOYA_CO2)
        self._comando(r, "claraboya", claraboya)

        ahora = self.reloj()
        if aforo >= AFORO_ACTIVAR:
            self._afluencia_hasta[r] = ahora + MANTENER_AFLUENCIA_S
        afluencia = ahora < self._afluencia_hasta.get(r, float("-inf"))
        ac_prev = bool(self.cmd.get((r, "ac"), False))
        umbral = IC_AC_AFLUENCIA if afluencia else IC_AC_ON
        if ahorro:
            umbral += DELTA_AHORRO
        elif preenfriar:
            umbral -= DELTA_PREENFRIAR
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
