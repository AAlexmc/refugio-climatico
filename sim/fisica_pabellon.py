"""Física de ventilación del Pabellón Venturi (modelo de orden cero, unidades SI).

Geometría (diseño del equipo): planta L × 2,4 m, muros de vidrio de 2,75 m, techo semicircular
de radio 1,35 m con una abertura longitudinal en la cima (garganta Venturi), rejillas bajas a
ambos lados (entrada de aire), extractores en la cima y boquillas de nebulización.

Mecanismos:
1. **Venturi / succión del viento.** El viento transversal se acelera sobre el techo curvo.
   En flujo potencial sobre un semicilindro la velocidad en la cima es 2·v; con capa límite
   real tomamos K_CIMA = 1,6. Por Bernoulli el coeficiente de presión allí es
   Cp = 1 − K² ≈ −1,56: la garganta queda en depresión Δp_v = ½·ρ·v²·|Cp| y succiona el aire.
2. **Efecto chimenea.** Aire interior más caliente que el exterior: Δp_s = ρ·g·H·ΔT/T_ext,
   con H = desnivel entre rejillas bajas y garganta.
3. **Caudal natural.** Orificios en serie (rejillas + garganta): Q = Cd·A_eff·√(2·Δp/ρ),
   1/A_eff² = 1/A_in² + 1/A_out². La garganta se abre con la «claraboya» (0..1) del control.
4. **Extractores.** Caudal fijo por extractor cuando el ventilador está encendido.
5. **Nebulización.** Agua evaporada m_w → calor latente m_w·h_fg, limitado por la depresión de
   bulbo húmedo (no se puede enfriar por debajo de T_bh; eficacia 70 %).
6. **Sensación térmica.** Temperatura aparente de Steadman (BOM Australia):
   AT = T + 0,33·e − 0,70·v − 4,00 (e en hPa), que incluye humedad y velocidad del aire.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

RHO = 1.2          # kg/m³ aire
CP = 1005.0        # J/(kg·K)
G = 9.81
CD = 0.61          # coeficiente de descarga de orificio
K_CIMA = 1.6       # v_cima / v_viento sobre el semicilindro
H_FG = 2.45e6      # J/kg calor latente de vaporización
Q_EXTRACTOR = 0.30  # m³/s por extractor de techo (Ø300 mm)
L_H_BOQUILLA = 3.8  # L/h por boquilla de alta presión
EFIC_EVAP = 0.7


@dataclass(frozen=True)
class Pabellon:
    largo: float = 6.0
    ancho: float = 2.4
    alto_muro: float = 2.75

    @property
    def radio(self) -> float:             # bóveda semicircular apoyada sobre los muros (+15 cm de vuelo)
        return self.ancho / 2 + 0.15

    @property
    def volumen(self) -> float:
        return self.largo * self.ancho * self.alto_muro + self.largo * math.pi * self.radio ** 2 / 2

    @property
    def area_entrada(self) -> float:      # rejillas bajas en los 2 lados, 0,25 m de alto, 50 % libre
        return 2 * self.largo * 0.25 * 0.5

    @property
    def area_garganta(self) -> float:     # abertura de la cima (0,22 m de ancho)
        return self.largo * 0.22

    @property
    def altura_chimenea(self) -> float:   # rejillas (0,15 m) -> garganta (≈4,0 m)
        return self.alto_muro + self.radio - 0.15

    @property
    def extractores(self) -> int:
        return max(1, round(self.largo / 2))

    @property
    def boquillas(self) -> int:
        return int((self.largo - 0.9) / 0.7) + 1

    @property
    def area_vidrio(self) -> float:
        return 2 * self.largo * 2.2 + 2 * (self.ancho * 2.2 + math.pi * self.radio ** 2 / 2)

    @property
    def area_techo(self) -> float:
        return self.largo * math.pi * self.radio


def pabellon_de_modulos(n: int) -> Pabellon:
    """1, 2, 3 módulos -> 4, 6, 8 m de largo."""
    return Pabellon(largo=2.0 * (min(3, max(1, int(n))) + 1))


LARGOS = (4.0, 6.0, 8.0, 10.0, 12.0)
ANCHOS = (2.4, 3.6, 4.8)


def pabellon(largo: float = 6.0, ancho: float = 2.4) -> Pabellon:
    """Ampliable a lo largo (4–12 m, tramos de 2 m) y a lo ancho (2,4 / 3,6 / 4,8 m)."""
    largo = min(LARGOS, key=lambda x: abs(x - float(largo)))
    ancho = min(ANCHOS, key=lambda x: abs(x - float(ancho)))
    return Pabellon(largo=largo, ancho=ancho)


def presion_venturi(viento: float) -> float:
    """Depresión (Pa, positiva = succión) en la garganta por el viento transversal."""
    return 0.5 * RHO * viento ** 2 * (K_CIMA ** 2 - 1)


def presion_chimenea(p: Pabellon, t_int: float, t_ext: float) -> float:
    """Pa; positiva si el interior está más caliente (el aire sube y sale por la cima)."""
    return RHO * G * p.altura_chimenea * (t_int - t_ext) / (t_ext + 273.15)


def caudal(p: Pabellon, t_int: float, t_ext: float, viento: float, apertura: float,
           ventilador: bool) -> dict:
    dp_v = presion_venturi(viento) * min(1.0, max(0.0, apertura) * 4)   # sin garganta no hay succión
    dp_s = presion_chimenea(p, t_int, t_ext)
    dp = max(0.0, dp_v + dp_s)
    a_out = max(1e-3, p.area_garganta * max(0.0, min(1.0, apertura)))  # cerrada: solo infiltración
    a_eff = 1.0 / math.sqrt(1.0 / p.area_entrada ** 2 + 1.0 / a_out ** 2)
    q_nat = CD * a_eff * math.sqrt(2.0 * dp / RHO)
    q_fan = p.extractores * Q_EXTRACTOR if ventilador else 0.0
    q = q_nat + q_fan
    v_in = q / p.area_entrada
    return {"dp_venturi": dp_v, "dp_chimenea": dp_s, "caudal": q, "caudal_natural": q_nat,
            "caudal_extractores": q_fan, "renovaciones_h": q * 3600.0 / p.volumen,
            "v_entrada": v_in, "v_ocupante": min(1.5, 0.3 * v_in)}


def bulbo_humedo(t: float, hr: float) -> float:
    """Temperatura de bulbo húmedo (°C), fórmula de Stull (2011)."""
    hr = min(max(hr, 5.0), 99.0)
    return (t * math.atan(0.151977 * math.sqrt(hr + 8.313659)) + math.atan(t + hr)
            - math.atan(hr - 1.676331) + 0.00391838 * hr ** 1.5 * math.atan(0.023101 * hr) - 4.686035)


def enfriamiento_evaporativo(p: Pabellon, q: float, t: float, hr: float, activo: bool) -> float:
    """W retirados del aire por la nebulización (limitado por el bulbo húmedo)."""
    if not activo or q <= 0:
        return 0.0
    m_w = p.boquillas * L_H_BOQUILLA / 3600.0       # kg/s
    maximo = RHO * CP * q * EFIC_EVAP * max(0.0, t - bulbo_humedo(t, hr))
    return min(m_w * H_FG, maximo)


def temperatura_aparente(t: float, hr: float, v: float) -> float:
    e = hr / 100.0 * 6.105 * math.exp(17.27 * t / (237.7 + t))
    return t + 0.33 * e - 0.70 * v - 4.00


def viento_barcelona(h: float) -> float:
    """Brisa marina típica de verano: ~1,5 m/s de noche, ~4 m/s a media tarde."""
    return 1.5 + 2.5 * max(0.0, math.sin((h - 10.0) / 10.0 * math.pi))
