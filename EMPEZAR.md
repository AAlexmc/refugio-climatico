# Cómo empezar — paso a paso por ordenador

| Ordenador | IA | Qué hace | Ficha |
|---|---|---|---|
| **1** | Claude Code (terminal) | Visión RealSense (aforo + desmayo) · maqueta ESP32 | [`equipo/ordenador-1.md`](equipo/ordenador-1.md) |
| **2** | **Claude Code de escritorio** (app) | Control + servidor + simulador térmico/energía + `/api/metricas` | [`equipo/ordenador-2.md`](equipo/ordenador-2.md) |
| **3** | **Gemini** (Gemini CLI) | Gemelo 3D + configurador + pestaña Métricas + app ciudadana + pitch | [`equipo/ordenador-3.md`](equipo/ordenador-3.md) |

## 0. Una vez por persona (todos)

1. Acepta la invitación al repo: https://github.com/AAlexmc/refugio-climatico/invitations
   (sin aceptarla no puedes hacer `push`).
2. Necesitas **git** y **Python 3.10+**. Comprueba: `git --version` y `python --version`
   (en Linux/Mac puede ser `python3`).
3. Descarga el repo e instala:

   **Linux / Mac**
   ```bash
   git clone https://github.com/AAlexmc/refugio-climatico.git
   cd refugio-climatico
   ./scripts/instalar.sh
   ```
   **Windows (PowerShell)**
   ```powershell
   git clone https://github.com/AAlexmc/refugio-climatico.git
   cd refugio-climatico
   powershell -ExecutionPolicy Bypass -File .\scripts\instalar.ps1
   ```
   Tiene que acabar con `... passed` y `OK. Arranca: ...`.
4. Comprueba que se ve: arranca `.venv/bin/python -m servidor.app`
   (Windows: `.\.venv\Scripts\python -m servidor.app`) y abre http://127.0.0.1:8000.
   Ciérralo con Ctrl+C.

---

## Ordenador 2 — Claude Code de escritorio

1. Abre la app **Claude** de escritorio → pestaña **Code**.
2. **Selecciona la carpeta** `refugio-climatico` que acabas de clonar (botón de elegir carpeta/proyecto).
3. Escribe solo:
   ```
   Ordenador 2
   ```
4. Claude lee `CLAUDE.md` → `AGENTS.md` → tu ficha y empieza. Acepta los permisos que pida
   (editar ficheros, ejecutar `git`, `python`). Si te pregunta algo, contesta corto.
5. Cuando acabe un hito te dirá que ha abierto un PR. Si no tiene `gh`, te dará un enlace
   para abrir el PR en la web de GitHub: ábrelo y pulsa **Create pull request**.

## Ordenador 3 — Gemini (Gemini CLI)

Gemini tiene que trabajar **dentro de la carpeta del repo** para poder leer y editar ficheros.
La web gemini.google.com NO sirve para esto (no ve tus ficheros).

1. Instala Node.js 20+ (https://nodejs.org) y luego Gemini CLI:
   ```bash
   npm install -g @google/gemini-cli
   ```
2. Entra en el repo y arranca:
   ```bash
   cd refugio-climatico
   gemini
   ```
   La primera vez inicia sesión con tu cuenta de Google.
3. Escribe solo:
   ```
   Ordenador 3
   ```
   Gemini carga `GEMINI.md` → `AGENTS.md` y empieza. Si no parece haber leído las instrucciones,
   escribe: `Lee GEMINI.md, AGENTS.md y equipo/ordenador-3.md y empieza como Ordenador 3`.
4. Acepta cuando pida ejecutar comandos (`git`, `python`) o escribir ficheros.
5. Para ver tu trabajo: el servidor (paso 0.4) y abre http://127.0.0.1:8000/gemelo.html,
   `/metricas.html`, `/mapa.html` según lo que vaya creando.

## Ordenador 1 — Claude Code (terminal)

```bash
cd refugio-climatico && claude
```
y escribe `Ordenador 1`. La RealSense va en un puerto **USB 3** (azul).

---

## Reglas rápidas para las personas (las IAs ya las conocen)

- Cada ordenador trabaja en **su rama** y abre **PR** a `main`; nunca directo a `main`.
- Antes de empezar cada rato: `git pull` en `main` (la IA lo hace sola).
- **No subáis fotos ni vídeos de personas** al repo.
- Para proponer una mejora a otro ordenador: pídeselo a tu IA → la escribe en `propuestas/`.
- Para ver el servidor de otro ordenador en la misma wifi: el otro arranca con `--host 0.0.0.0`
  y tú abres `http://<su-ip>:8000`.

## Si algo falla

| Problema | Solución |
|---|---|
| `git push` → *permission denied* / 403 | No has aceptado la invitación (paso 0.1) |
| `git push` pide usuario/contraseña | Usa un token: GitHub → Settings → Developer settings → Personal access tokens, o instala `gh` y haz `gh auth login` |
| `instalar.ps1` no se ejecuta | Usa la línea con `-ExecutionPolicy Bypass` del paso 0.3 |
| `python` no encontrado (Windows) | Instala Python desde python.org marcando «Add to PATH» |
| `gh` no está | No pasa nada: la IA hace `git push` y te da el enlace para abrir el PR en la web |
| Tests en rojo tras `git pull` | Díselo a tu IA: «los tests fallan tras el pull, arréglalo o avisa al dueño» |
