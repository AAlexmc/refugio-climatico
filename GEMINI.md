# Instrucciones para Gemini (Ordenador 3)

@AGENTS.md

## Resumen por si el import anterior no se cargó

- Lee ENTERO `AGENTS.md`, luego `docs/reto.md`, `docs/contratos.md` y `equipo/ordenador-3.md`.
- Si el usuario escribe «Ordenador 3» (o cualquier número): sigue el «Orden de trabajo» de
  `equipo/ordenador-N.md` y empieza YA, sin preguntar.
- Flujo git: `git checkout main && git pull` → `git checkout -b o3/<tema>` → cambios →
  test (`.venv/bin/python -m pytest -q`, Windows `.\.venv\Scripts\python -m pytest -q`) →
  `git add <rutas concretas>` → `git commit -m "o3: ..."` → `git push -u origin o3/<tema>` →
  PR con `gh pr create --fill` o, sin `gh`, dar al usuario el enlace
  `https://github.com/AAlexmc/refugio-climatico/compare/o3/<tema>?expand=1`.
- Solo editas tus carpetas (`docs/contratos.md` § Propiedad): `web/gemelo.*`, `web/configurador.*`,
  `web/metricas.*`, `web/mapa.*`, `web/modelos/`, `pitch/`, `datos/kits.json`, `README.md`.
- Sin CDN: Three.js está en `web/vendor/` (`import * as THREE from "./vendor/three.module.js"`).
- Datos en vivo: WebSocket `ws://<host>/ws`, eventos `{"tipo","valor","fuente","refugio","t","unidad"}`
  (tipos en `nucleo/evento.py`). Ejemplo de consumo: `web/index.html`.
- Nunca guardar fotos/vídeo de personas. Nunca push a `main`.
