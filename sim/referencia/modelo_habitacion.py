"""REFERENCIA (proyecto anterior, Hospital en casa): no lo importa nadie;
Ordenador 2 lo usa como base para sim/termico.py del refugio.

Modelo térmico RC de una habitación en ola de calor + políticas de control.

Modelo de 2 nodos: aire (con mobiliario ligero) y masa térmica interior
(forjado, paredes). Paso de 60 s, 5 días. Todos los números son SUPUESTOS
representativos, no mediciones ni datos de una fuente concreta:

- Exterior: ola de calor tipo Barcelona en julio. Senoide diaria con máximo
  ~35 °C a las 16 h y mínimo ~25 °C a las 4 h (noches tropicales), pequeña
  variación entre días. HR anticorrelacionada con la temperatura (~40 % por
  la tarde, ~75 % de madrugada).
- Precio de la luz: perfil horario tipo PVPC de verano, en €/kWh con peajes
  e impuestos incluidos, igual los 5 días. Valle barato 0-8 h y mediodía
  solar (11-15 h), punta 19-22 h. Valores ilustrativos.
- Habitación ~12 m² / 30 m³, ático mal aislado, ventana oeste de 2 m² con
  persiana a medias (ganancia solar con perfil diario).
- Ganancias internas: paciente 80 W + concentrador de O₂ 300 W (consumo
  eléctrico que acaba como calor).
- Climatización: split inverter pequeño (modula), 2,5 kW de frío máx., COP 3 a 35 °C exterior
  (baja ~0,08 por cada °C más). El ventilador no se modela aparte: el
  actuador `rele` representa el equipo de climatización.
- Apagón programable (por defecto día 3, 19:00-21:00): sin red no hay
  climatización. El concentrador solo sigue si la política `sistema` tiene
  SAI/batería (1 kWh, rendimiento del inversor 90 %).
- Se simula un día de calentamiento previo (no contado) para no arrancar
  con la habitación en equilibrio artificial.

Políticas:
- `nada`: sin aire, ventana cerrada, sin SAI.
- `sistema`: preenfría a 25 °C en horas baratas, ventila de noche si
  exterior < interior, mantiene el índice de calor < 27 °C y protege el
  concentrador con el SAI durante el apagón.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from nucleo.confort import indice_calor

SUBPASOS = 6   # subpasos térmicos por paso de 60 s
POLITICAS = ("nada", "convencional", "sistema")

# Precio PVPC verano ilustrativo (€/kWh) por hora 0..23.
PRECIO_HORARIO = (
    0.10, 0.09, 0.09, 0.09, 0.09, 0.10, 0.10, 0.12,   # 0-7 valle
    0.14, 0.12, 0.10, 0.08, 0.07, 0.07, 0.08, 0.10,   # 8-15 (mediodía solar barato)
    0.13, 0.17, 0.21, 0.27, 0.30, 0.29, 0.24, 0.14,   # 16-23 (punta 19-22)
)


@dataclass
class Parametros:
    # Tiempo
    dt: float = 60.0                    # s por paso
    dias: int = 5
    # Térmicos (J/K y W/K)
    c_aire: float = 1.0e5               # aire + mobiliario ligero
    c_masa: float = 5.0e6               # forjado/paredes interiores
    h_aire_masa: float = 320.0          # acoplamiento aire-masa
    ua_envolvente: float = 200.0        # fachada+cubierta+infiltración
    ua_ventilacion: float = 70.0        # extra con ventana abierta (ventilación cruzada)
    # Solar
    area_ventana: float = 2.0           # m²
    factor_solar: float = 0.30          # g * persiana
    irradiancia_pico: float = 600.0     # W/m² sobre la ventana
    solar_a_aire: float = 0.3           # resto va a la masa
    # Ganancias internas
    q_paciente: float = 80.0            # W
    p_concentrador: float = 300.0       # W eléctricos (= calor)
    # Climatización
    q_frio: float = 2500.0              # W térmicos
    cop_ref: float = 3.0                # COP a 35 °C exterior
    cop_pendiente: float = 0.08         # pérdida de COP por °C exterior sobre 35
    # SAI
    sai_kwh: float = 1.0                # 0 = sin SAI
    sai_rend: float = 0.90              # rendimiento inversor/cargador
    sai_carga_w: float = 200.0          # potencia de recarga desde red
    # Humedad
    tau_humedad: float = 7200.0         # s, renovación de aire
    deshum_ac: float = 0.8              # factor de humedad absoluta con aire encendido
    # Exterior
    t_media: float = 30.0
    t_amplitud: float = 5.0
    t_dia: tuple = (-0.5, 0.0, 0.5, 0.0, -0.5)   # desviación por día
    hr_media: float = 58.0
    hr_amplitud: float = 17.0
    # Apagón programado (día base 0; None = sin apagón)
    apagon_dia: int | None = 2
    apagon_ini_h: float = 19.0
    apagon_fin_h: float = 21.0
    # Control `sistema`
    t_preenfriado: float = 25.0         # °C en horas baratas
    precio_barato: float = 0.11         # €/kWh: por debajo = hora barata
    t_consigna: float = 25.5            # °C en horas intermedias (mantiene índice < 27 °C)
    precio_caro: float = 0.20           # €/kWh: por encima = punta
    t_punta: float = 26.0               # °C en punta: deja derivar mientras el índice lo permita
    ic_limite_punta: float = 26.2       # en punta, si el índice llega aquí vuelve a t_consigna
    sai_reserva_kwh: float = 0.75       # el SAI solo se descarga en punta por encima de esto.
                                        # 0,75 kWh ≈ 2 h 15 min de concentrador: la seguridad
                                        # del paciente manda sobre el ahorro
    # Control `convencional`: termostato fijo, como un usuario normal con split
    t_convencional: float = 25.0
    kp_frio: float = 2500.0             # W/K: split inverter modula su potencia
    ic_objetivo: float = 26.5           # con ventana abierta, el aire solo entra si índice < esto
    noche: tuple = (21.0, 9.0)          # ventilación permitida entre estas horas
    t_ini: float = 28.0
    # Tarifa: 24 precios €/kWh por hora (vacío = perfil PVPC ilustrativo). El
    # catálogo la rellena con la tarifa real por periodos (datos/equipos.json).
    tarifa_horaria: tuple = ()


# -- exterior ----------------------------------------------------------------
def hora_del_dia(t_s: float) -> float:
    return (t_s % 86400.0) / 3600.0


def t_exterior(t_s: float, p: Parametros) -> float:
    dia = int(t_s // 86400) % p.dias
    fase = 2 * math.pi * (hora_del_dia(t_s) - 16.0) / 24.0
    return p.t_media + p.t_dia[dia % len(p.t_dia)] + p.t_amplitud * math.cos(fase)


def hr_exterior(t_s: float, p: Parametros) -> float:
    fase = 2 * math.pi * (hora_del_dia(t_s) - 16.0) / 24.0
    return p.hr_media - p.hr_amplitud * math.cos(fase)


def irradiancia(t_s: float, p: Parametros) -> float:
    """W/m² sobre la ventana oeste: campana 9-20 h, pico ~14:30."""
    h = hora_del_dia(t_s)
    if not 9.0 <= h <= 20.0:
        return 0.0
    return p.irradiancia_pico * math.sin(math.pi * (h - 9.0) / 11.0) ** 1.2


def luz_exterior(t_s: float) -> float:
    """0..1 de luz diurna (sensor LDR de la habitación)."""
    h = hora_del_dia(t_s)
    if not 6.5 <= h <= 21.0:
        return 0.0
    return math.sin(math.pi * (h - 6.5) / 14.5)


def precio(t_s: float, p: "Parametros | None" = None) -> float:
    tabla = p.tarifa_horaria if p is not None and p.tarifa_horaria else PRECIO_HORARIO
    return tabla[int(hora_del_dia(t_s)) % 24]


def presencia(t_s: float) -> bool:
    """Paciente en la habitación y despierto/moviéndose de 8 a 22 h,
    salvo un paseo 15:00-15:30. De noche duerme (PIR sin movimiento)."""
    h = hora_del_dia(t_s)
    return 8.0 <= h < 22.0 and not 15.0 <= h < 15.5


def _w_abs(t_c: float, hr: float) -> float:
    """Humedad absoluta (kg/kg) a partir de T y HR (Magnus)."""
    es = 611.2 * math.exp(17.62 * t_c / (243.12 + t_c))
    e = max(0.0, min(hr, 100.0)) / 100.0 * es
    return 0.622 * e / (101325.0 - e)


def _hr_desde_w(t_c: float, w: float) -> float:
    e = w * 101325.0 / (0.622 + w)
    es = 611.2 * math.exp(17.62 * t_c / (243.12 + t_c))
    return max(5.0, min(100.0, 100.0 * e / es))


# -- estado y paso -------------------------------------------------------------
@dataclass
class Muestra:
    t: float            # s desde inicio
    t_ext: float
    t_int: float
    hr_int: float
    ic_int: float       # índice de calor interior
    ic_ext: float
    precio: float       # €/kWh
    red: bool
    ac: bool
    ventana: bool
    p_clima_w: float
    p_med_w: float      # potencia del concentrador (0 si sin O₂)
    p_red_w: float      # consumo total de red
    sai_kwh: float
    sin_o2: bool
    luz: float
    presencia: bool


class Simulador:
    """Avanza el modelo paso a paso. Lo usan `simular()` y `FuenteSim`."""

    def __init__(self, politica: str = "sistema", params: Parametros | None = None,
                 *, t0: float = 0.0, calentar: bool = True) -> None:
        if politica not in POLITICAS:
            raise ValueError(f"política desconocida: {politica!r}")
        self.politica = politica
        self.p = params or Parametros()
        self.t = t0
        self.t_aire = self.t_masa = self.p.t_ini
        self.w_int = _w_abs(self.p.t_ini, 60.0)
        self.ac = False
        self.ventana = False
        self.sai = self.p.sai_kwh if politica == "sistema" else 0.0
        if calentar:
            self._calentar(t0)

    def _calentar(self, t0: float) -> None:
        """Un día previo (mismo perfil que el día de arranque, sin apagón)."""
        apagon, self.p.apagon_dia = self.p.apagon_dia, None
        try:
            self.t = (t0 // 86400) * 86400.0
            for _ in range(int(86400 / self.p.dt)):
                self.paso()
        finally:
            self.p.apagon_dia = apagon
            self.t = t0

    def red_programada(self, t_s: float) -> bool:
        p = self.p
        if p.apagon_dia is None:
            return True
        dia = int(t_s // 86400) % p.dias
        return not (dia == p.apagon_dia and p.apagon_ini_h <= hora_del_dia(t_s) < p.apagon_fin_h)

    def paso(self, *, red_externa: bool = True, rele_manual: bool | None = None) -> Muestra:
        p, t = self.p, self.t
        t_ext, hr_ext = t_exterior(t, p), hr_exterior(t, p)
        h = hora_del_dia(t)
        red = red_externa and self.red_programada(t)
        pr = precio(t, p)
        hr_int = _hr_desde_w(self.t_aire, self.w_int)
        ic = indice_calor(self.t_aire, hr_int)

        # --- control: consigna (inverter modula) o relé manual a plena potencia ---
        t_set: float | None = None
        q_fijo: float | None = None
        ventana = False
        if self.politica == "sistema":
            ini, fin = p.noche
            es_noche = h >= ini or h < fin
            ventana = es_noche and t_ext < self.t_aire - 1.0
            if self.ventana and es_noche and t_ext < self.t_aire:   # histéresis
                ventana = True
            if pr <= p.precio_barato:
                t_set = p.t_preenfriado
            elif pr >= p.precio_caro and ic < p.ic_limite_punta:
                t_set = p.t_punta
            else:
                t_set = p.t_consigna
            if ventana and ic < p.ic_objetivo:
                t_set = None
        elif self.politica == "convencional":
            t_set = p.t_convencional
        if rele_manual is not None:
            t_set, q_fijo = None, (p.q_frio if rele_manual else 0.0)
        if not red:
            t_set, q_fijo = None, 0.0

        # --- eléctrico (equipo médico y SAI) ---
        carga = p.p_concentrador
        sin_o2 = False
        p_red = 0.0
        hay_sai = self.politica == "sistema" and p.sai_kwh > 0
        if red:
            p_red = carga
            punta = pr >= p.precio_caro
            need = carga / p.sai_rend * p.dt / 3.6e6
            if hay_sai and punta and self.sai - need >= p.sai_reserva_kwh:
                # flexibilidad: en punta el concentrador tira del SAI, no de la red
                self.sai -= need
                p_red = 0.0
            elif hay_sai and self.sai < p.sai_kwh and pr <= p.precio_barato:
                w = min(p.sai_carga_w, (p.sai_kwh - self.sai) * 3.6e6 / p.dt / p.sai_rend)
                self.sai += w * p.sai_rend * p.dt / 3.6e6
                p_red += w
        else:
            need = carga / p.sai_rend * p.dt / 3.6e6
            if hay_sai and self.sai >= need:
                self.sai -= need
            else:
                sin_o2 = True
        p_med = 0.0 if sin_o2 else carga

        # --- térmico: subpasos para que el lazo proporcional sea estable ---
        q_sol = p.area_ventana * p.factor_solar * irradiancia(t, p)
        q_int = p.q_paciente + p_med
        g_ext = p.ua_envolvente + (p.ua_ventilacion if ventana else 0.0)
        n = SUBPASOS
        ds = p.dt / n
        q_medio = 0.0
        for _ in range(n):
            if q_fijo is not None:
                q_ac = q_fijo
            elif t_set is not None:
                q_ac = max(0.0, min(p.q_frio, p.kp_frio * (self.t_aire - t_set)))
            else:
                q_ac = 0.0
            q_medio += q_ac / n
            q_aire = (g_ext * (t_ext - self.t_aire) + p.h_aire_masa * (self.t_masa - self.t_aire)
                      + q_int + p.solar_a_aire * q_sol - q_ac)
            q_masa = p.h_aire_masa * (self.t_aire - self.t_masa) + (1 - p.solar_a_aire) * q_sol
            self.t_aire += q_aire * ds / p.c_aire
            self.t_masa += q_masa * ds / p.c_masa
        ac = q_medio > 50.0
        self.ac, self.ventana = ac, ventana
        cop = max(2.0, min(4.5, p.cop_ref - p.cop_pendiente * (t_ext - 35.0)))
        p_clima = q_medio / cop
        p_red += p_clima
        # humedad: relaja hacia la absoluta exterior (más seca con el aire encendido)
        w_obj = _w_abs(t_ext, hr_ext) * (p.deshum_ac if ac else 1.0)
        self.w_int += (w_obj - self.w_int) * min(1.0, p.dt / p.tau_humedad)

        m = Muestra(t=t, t_ext=t_ext, t_int=self.t_aire, hr_int=hr_int, ic_int=ic,
                    ic_ext=indice_calor(t_ext, hr_ext), precio=pr, red=red, ac=ac,
                    ventana=ventana, p_clima_w=p_clima, p_med_w=p_med, p_red_w=p_red,
                    sai_kwh=self.sai, sin_o2=sin_o2, luz=luz_exterior(t),
                    presencia=presencia(t))
        self.t += p.dt
        return m


@dataclass
class Metricas:
    horas_ic27: float
    horas_ic32: float
    kwh: float
    euros: float
    min_sin_o2: float
    ic_max: float
    kwh_punta: float = 0.0     # kWh comprados con precio >= precio_caro


@dataclass
class Resultado:
    politica: str
    serie: list[Muestra] = field(default_factory=list)
    metricas: Metricas | None = None


def simular(politica: str, params: Parametros | None = None) -> Resultado:
    p = params or Parametros()
    sim = Simulador(politica, p)
    serie = [sim.paso() for _ in range(int(p.dias * 86400 / p.dt))]
    h = p.dt / 3600.0
    m = Metricas(
        horas_ic27=sum(h for s in serie if s.ic_int >= 27.0),
        horas_ic32=sum(h for s in serie if s.ic_int >= 32.0),
        kwh=sum(s.p_red_w for s in serie) * h / 1000.0,
        euros=sum(s.p_red_w * h / 1000.0 * s.precio for s in serie),
        min_sin_o2=sum(p.dt / 60.0 for s in serie if s.sin_o2),
        ic_max=max(s.ic_int for s in serie),
        kwh_punta=sum(s.p_red_w for s in serie if s.precio >= p.precio_caro) * h / 1000.0,
    )
    return Resultado(politica, serie, m)


