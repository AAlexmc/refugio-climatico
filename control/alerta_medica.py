"""Aviso al servicio médico (BASE — Ordenador 2).

En la demo NO se llama al 061/112 real. Por defecto registra el aviso en
`datos/avisos_medicos.jsonl` y, si existe la variable de entorno
`OASI_WEBHOOK` (p. ej. un bot de Telegram/ntfy del equipo), hace POST con el JSON.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

RUTA = Path(__file__).resolve().parent.parent / "datos" / "avisos_medicos.jsonl"
log = logging.getLogger(__name__)


def _post(url: str, cuerpo: dict) -> None:
    try:
        import httpx
        httpx.post(url, json=cuerpo, timeout=5)
    except Exception as e:  # el aviso no puede tumbar el control
        log.warning("webhook médico falló: %s", e)


def avisar(refugio: str, mensaje: str) -> dict:
    cuerpo = {"t": time.time(), "refugio": refugio, "mensaje": mensaje, "destino": "061 (simulado)"}
    try:
        RUTA.parent.mkdir(parents=True, exist_ok=True)
        with RUTA.open("a", encoding="utf-8") as f:
            f.write(json.dumps(cuerpo, ensure_ascii=False) + "\n")
    except OSError as e:
        log.warning("no se pudo registrar aviso: %s", e)
    url = os.environ.get("OASI_WEBHOOK")
    if url:
        threading.Thread(target=_post, args=(url, cuerpo), daemon=True).start()
    log.warning("AVISO MÉDICO %s: %s", refugio, mensaje)
    return cuerpo
