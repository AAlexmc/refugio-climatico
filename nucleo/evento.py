"""Esquema único de evento. Real y simulado producen lo mismo.

Un evento = una medida o una decisión de un refugio en un instante.
CONTRATO COMPARTIDO por los 3 ordenadores (ver docs/contratos.md): añadir un
tipo nuevo = PR pequeño que toca SOLO este fichero + docs/contratos.md.
Toda fuente (ESP32, simulador, RealSense, reglas) publica `Evento`; el
panel y el gemelo 3D solo consumen JSON con esta forma.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

# tipo -> unidad canónica. Un tipo fuera de esta tabla es un error de
# programación, no un dato raro: se rechaza al construir el evento.
TIPOS: dict[str, str] = {
    # --- clima (ESP32 real o sim/termico.py) ---
    "temp": "°C",              # temperatura interior del refugio
    "temp_ext": "°C",          # temperatura exterior (calle)
    "humedad": "%",            # humedad relativa interior
    "humedad_ext": "%",        # humedad relativa exterior
    "indice_calor": "°C",      # temperatura aparente interior (calculada)
    "radiacion": "W/m²",       # irradiancia solar sobre la cúpula
    "co2": "ppm",              # calidad del aire interior
    "luz": "",                 # 0..1 (LDR normalizado)
    "lluvia": "",              # bool
    "viento": "m/s",
    # --- visión (ordenador 1) ---
    "aforo": "personas",       # int: personas dentro ahora (RealSense + detector con etiquetas)
    "personas": "",            # list[{"id": int, "x": m, "z": m, "etiqueta": str}] SIN imagen (gemelo 3D)
    "pose": "m",               # dict {"puntos": [[x,y,z]*33], "cadera_z": m, "visible": bool}
    "caida": "",               # bool: alguien en el suelo
    "desmayo": "",             # dict {"activo": bool, "segundos_inmovil": s, "zona": str}
    # --- actuadores (estado real, lo publica quien los mueve) ---
    "claraboya": "",           # 0..1 apertura (0 cerrada, 1 abierta)
    "ac": "",                  # bool: climatización encendida
    "nebulizador": "",         # bool: humidificador/nebulización evaporativa
    "ventilador": "",          # bool
    "potencia": "W",           # consumo eléctrico total del refugio
    "solar": "W",              # generación de las placas FV montadas fuera, en la corona de la cúpula
    "bateria": "%",            # estado de carga de la batería del refugio (0..100)
    "red": "W",                # importación de red (+) / exportación (-); 0 = isla con batería
    "rele": "",                # bool: compat. firmware ESP32 (relé genérico)
    # --- sistema ---
    "modulos": "",             # dict {"kit": "parada_bus"|"terraza_comunitaria"|"terraza_privada", "n": int, "area_m2": float}
    "alerta": "",              # dict {"nivel", "codigo", "mensaje"}
    "comando": "",             # dict {"destino", "valor"} PC -> actuador
    "estado_fuente": "",       # dict {"conectada": bool, "detalle": str}
    "modo_pose": "",           # dict {"modo": "camara"|"sim", "pedido", "auto", "camara_ok"}
    "guion": "",               # dict {"paso", "total", "titulo", "texto"}; demo guiada
    "presencia": "",           # bool (PIR)
}

NIVELES = ("info", "aviso", "critico")
FUENTES = ("esp32", "sim", "realsense", "webcam", "yolo", "reglas", "panel", "app")


@dataclass(frozen=True)
class Evento:
    tipo: str
    valor: Any
    fuente: str
    refugio: str = "R1"
    t: float = field(default_factory=time.time)
    unidad: str = ""

    def __post_init__(self) -> None:
        if self.tipo not in TIPOS:
            raise ValueError(f"tipo desconocido: {self.tipo!r}")
        if self.fuente not in FUENTES:
            raise ValueError(f"fuente desconocida: {self.fuente!r}")
        if not self.unidad:
            object.__setattr__(self, "unidad", TIPOS[self.tipo])
        if self.tipo == "alerta":
            if not isinstance(self.valor, dict) or self.valor.get("nivel") not in NIVELES:
                raise ValueError(f"alerta mal formada: {self.valor!r}")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Evento":
        return cls(
            tipo=d["tipo"],
            valor=d["valor"],
            fuente=d["fuente"],
            refugio=d.get("refugio", "R1"),
            t=float(d.get("t", time.time())),
            unidad=d.get("unidad", ""),
        )


def alerta(nivel: str, codigo: str, mensaje: str, *, refugio: str = "R1",
           fuente: str = "reglas", t: float | None = None) -> Evento:
    """Atajo para crear una alerta. `codigo` estable (p.ej. "caida", "calor")
    para que el panel deduplique y la familia vea siempre el mismo icono."""
    kw = {} if t is None else {"t": t}
    return Evento("alerta", {"nivel": nivel, "codigo": codigo, "mensaje": mensaje},
                  fuente, refugio, **kw)
