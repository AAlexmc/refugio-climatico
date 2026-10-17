# Windows: crea .venv e instala dependencias.  Uso: .\scripts\instalar.ps1 [-Vision]
param([switch]$Vision)
Set-Location (Join-Path $PSScriptRoot "..")
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\pip install -q -r requirements.txt
if ($Vision) { .\.venv\Scripts\pip install -q -r requirements-vision.txt }
.\.venv\Scripts\python -m pytest -q
Write-Host "OK. Arranca: .\.venv\Scripts\python -m servidor.app  ->  http://127.0.0.1:8000"
