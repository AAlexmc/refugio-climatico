# OASI — instrucciones para la IA de cada ordenador

Proyecto Engihack 2026 (hoy, 17-10-2026, ESEIAAT). Refugio climático modular para la ciudad.
3 ordenadores con IA (2 personas cada uno) trabajan en paralelo sobre este repo. Lee esto ENTERO antes de tocar nada.

## ARRANQUE: «Ordenador N»

Si el usuario escribe **«Ordenador N»** (N = 1, 2 o 3; también «soy el ordenador N», «O2», «PC 2»…):

| N | Área |
|---|---|
| 1 | Visión RealSense (aforo + desmayo) + maqueta ESP32 |
| 2 | Control + servidor + simulador térmico/energía + `/api/metricas` |
| 3 | Gemelo 3D + configurador + pestaña Métricas + app ciudadana + pitch |


1. `git pull` en `main`.
2. Lee, en este orden: `docs/reto.md` → `docs/contratos.md` → `equipo/ordenador-N.md` →
   `propuestas/` (las que mencionen tu área o tu número).
3. Crea tu rama: `git checkout -b oN/<tema>` (p. ej. `o2/termico`).
4. **Empieza a trabajar YA siguiendo el «Orden de trabajo» de `equipo/ordenador-N.md`, sin preguntar.**
   Cada ordenador tiene 2 partes (A y B, una por persona): usa subagentes en paralelo si puedes.
   Pregunta al humano solo si una decisión destruye datos o cambia un contrato.
5. Dile al humano en 3 líneas qué vas a hacer y qué hardware/datos necesitarás de él.

Si el usuario no dice número, pregúntaselo (1–3) y nada más.

## Reglas de convivencia (3 IAs en un repo)

- **Solo editas tus carpetas** (tabla en `docs/contratos.md` § Propiedad). Para tocar algo de otro:
  escribe una propuesta (abajo) o un PR mínimo que el dueño revise.
- **Contratos** (`nucleo/evento.py`, `docs/contratos.md`): cambio = PR pequeño SOLO con eso,
  título `contrato: …`. Añadir un tipo nuevo es OK; renombrar/quitar uno NO sin acuerdo.
- **PR pequeños y frecuentes** (cada hito = 1 PR). `git pull --rebase origin main` antes de push.
  Nunca push a `main` ni `--force` a ramas ajenas. Merge con squash cuando el CI esté verde.
- `git add <rutas>` explícitas. Nunca `git add -A` (hay ficheros locales de calibración).
- Antes de PR: `python -m pytest -q` en verde. Código nuevo = test nuevo.
- Todo debe funcionar **offline** (wifi del evento poco fiable): nada de CDN, modelos en local.
- Sin hardware → fuente simulada con el MISMO contrato. Nunca inventar datos en una fuente "real".
- **Privacidad**: nunca guardar fotos/vídeo de personas. Solo números, etiquetas, esqueletos.
- Al cerrar cada hito: actualiza la sección «Estado» de TU `equipo/ordenador-N.md` (nadie más la toca).

## Propuestas de mejora entre IAs

Cualquier IA puede proponer mejoras para CUALQUIER área (también la suya):
- Añade un bloque al final de `propuestas/ordenador-N.md` (N = TU número, así no hay conflictos):
  ```
  ### [para O2] Título corto
  Problema: … · Propuesta: … · Impacto en el jurado: … · Coste: S/M/L
  ```
- Si `gh` está disponible, además: `gh issue create --label propuesta --title "[O2] …"`.
- Al empezar cada hito, revisa las propuestas dirigidas a ti y responde debajo
  (`→ O2: aceptada / descartada porque …`). Implementa las aceptadas en tu siguiente PR.
- Cada 2 h, dedica 5 min a leer los PRs de otros y proponer 1 mejora concreta.

## Comandos

```bash
./scripts/instalar.sh                    # venv + dependencias (una vez)
.venv/bin/python -m pytest -q            # tests
.venv/bin/python -m servidor.app         # todo simulado -> http://127.0.0.1:8000
.venv/bin/python -m servidor.app --pose realsense --ver-camara   # visión real
.venv/bin/python -m servidor.app --clima esp32 --puerto /dev/ttyACM0          # maqueta real
.venv/bin/python -m servidor.app --host 0.0.0.0   # para que otros PCs/el móvil lo vean en la red
```

## Estilo

Español en código, commits y docs. Python 3.10+, FastAPI, Three.js vendorizado en `web/vendor/`.
Comentarios cortos que expliquen el porqué. Commits: `oN: qué cambia`.
