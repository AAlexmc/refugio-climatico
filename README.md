# OASI — refugio climático modular · Engihack 2026

Refugio contra el calor que se monta en la calle y crece o se reduce por módulos: kit **parada de bus**,
**terraza comunitaria** y **terraza privada**. Cúpula clara sin efecto invernadero (vidrio/ETFE de control
solar + placas fotovoltaicas fuera en la corona), plantas, aire acondicionado, nebulización y claraboya
automática. Batería alimentada por el sol. Una cámara RealSense cuenta personas y detecta desmayos para
avisar al servicio médico, **sin guardar ninguna imagen**.

Detalle: [`docs/reto.md`](docs/reto.md) · Contratos: [`docs/contratos.md`](docs/contratos.md)

## Empezar en tu ordenador

```bash
git clone https://github.com/AAlexmc/refugio-climatico.git
cd refugio-climatico
./scripts/instalar.sh            # Windows: .\scripts\instalar.ps1   (añade --vision / -Vision en el PC de la cámara)
claude                           # o tu IA (Codex, Gemini, Copilot…: todas leen AGENTS.md)
```

Y escribe a la IA: **`Ordenador 1`**, **`Ordenador 2`** o **`Ordenador 3`**. Empieza sola su trabajo.

| Ordenador | Equipo (2 personas) | Ficha |
|---|---|---|
| 1 | Visión RealSense (aforo con etiquetas + desmayo) · maqueta ESP32 | [`equipo/ordenador-1.md`](equipo/ordenador-1.md) |
| 2 | Control + servidor + alertas · simulador térmico, placas FV, batería, `/api/metricas` | [`equipo/ordenador-2.md`](equipo/ordenador-2.md) |
| 3 | Gemelo 3D + configurador modular · pestaña Métricas, app ciudadana, cifras, pitch | [`equipo/ordenador-3.md`](equipo/ordenador-3.md) |

Las IAs se proponen mejoras entre ellas en [`propuestas/`](propuestas/).

## Arrancar la demo

```bash
.venv/bin/python -m servidor.app                    # todo simulado -> http://127.0.0.1:8000
.venv/bin/python -m servidor.app --pose realsense --ver-camara --clima esp32 --host 0.0.0.0
```

## Qué ya funciona (base reutilizada de nuestro proyecto anterior)
- Bus de eventos + servidor FastAPI/WebSocket, mismo contrato para datos reales y simulados.
- Pose 3D con RealSense + MediaPipe, detector de caídas entrenable (`/caida.html`), vista de cámara.
- Simulador de clima del refugio con placas FV + batería, reglas de control (claraboya, AC, nebulizador,
  alerta de desmayo) y panel en vivo. Firmware ESP32-S3 y puente serie.
