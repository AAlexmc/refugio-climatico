#!/usr/bin/env bash
# Crea .venv e instala dependencias. Uso: ./scripts/instalar.sh [--vision]
set -euo pipefail
cd "$(dirname "$0")/.."
# --system-site-packages: reusa mediapipe/pyrealsense2/ultralytics si ya están en el sistema
[ -d .venv ] || python3 -m venv --system-site-packages .venv
.venv/bin/pip install -q -r requirements.txt
if [ "${1:-}" = "--vision" ]; then .venv/bin/pip install -q -r requirements-vision.txt; fi
.venv/bin/python -m pytest -q
echo "OK. Arranca: .venv/bin/python -m servidor.app  ->  http://127.0.0.1:8000"
