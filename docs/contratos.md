# Contratos compartidos

Lo que une a los 3 ordenadores. Cambios: PR pequeño `contrato: …` (ver AGENTS.md).

## 1. Evento (`nucleo/evento.py`)
```json
{"tipo": "temp", "valor": 29.4, "fuente": "sim", "refugio": "R1", "t": 1792240000.0, "unidad": "°C"}
```
- `tipo` ∈ `TIPOS` (tabla en `nucleo/evento.py`, con unidad y forma del valor). Tipo desconocido = error.
- `fuente` ∈ `esp32 | sim | realsense | webcam | yolo | reglas | panel | app`.
- `refugio`: id del refugio (`R1` en la demo; la app/mapa usa varios).
- Real y simulado publican EXACTAMENTE lo mismo.

Tipos clave por área:
| Área | Publica | Consume |
|---|---|---|
| Visión (O1·A) | `aforo`, `personas` (`{id,x,y,etiqueta,estado}`), `pose`, `caida`, `desmayo` | `caida` (forzar en sim), `aforo` (fijar en sim) |
| Maqueta ESP32 (O1·B) | lo mismo que el sim pero medido (`fuente: esp32`) + estado actuadores | `comando` |
| Control (O2·A) | `comando`, `alerta`, `indice_calor` | todo lo medido |
| Simulador (O2·B) | `temp`, `temp_ext`, `humedad*`, `radiacion`, `solar`, `bateria`, `red`, `potencia`, estado actuadores | `comando`, `aforo`, `modulos` |
| Gemelo/configurador (O3·A) | `modulos` (kit elegido) | todo |
| Métricas/app (O3·B) | — | `/api/estado`, `/api/metricas`, `/api/refugios` |

## 2. Comandos (`tipo: "comando"`)
`valor = {"destino": D, "valor": V}`:
| destino | valor | quién obedece |
|---|---|---|
| `claraboya` | 0.0..1.0 | sim, ESP32 (servo) |
| `ac` | bool | sim, ESP32 (relé/LED azul) |
| `nebulizador` | bool | sim, ESP32 (relé/humidificador USB) |
| `ventilador` | bool | sim, ESP32 |
| `rele` | bool | ESP32 (compat.) |
Quien obedece publica después el estado real (`claraboya`, `ac`…) con su fuente.

## 3. Alertas (`tipo: "alerta"`)
`valor = {"nivel": "info"|"aviso"|"critico", "codigo": str, "mensaje": str}`.
Códigos estables: `desmayo`, `lleno`, `calor`, `bateria_baja`, `fuente_caida`.
`info` con el mismo código = resuelto.

## 4. API HTTP (`servidor/app.py`, puerto 8000)
| Ruta | Qué |
|---|---|
| `GET /api/estado` | último evento por (refugio, tipo) |
| `POST /api/evento` | inyectar un evento (ESP32 por WiFi, botones, otras apps) |
| `POST /api/comando` | `{"destino","valor"}` |
| `WS /ws` | flujo de eventos JSON (primero el estado actual) |
| `GET/POST /api/pose/modo`, `/api/caida/*`, `/camara.mjpg` | visión (O1) |
| `GET /api/metricas` | **O2·B lo crea**: resumen de escenario (ver `equipo/ordenador-2.md`) |
| `GET /api/kits` | **O3 lo crea**: catálogo de kits y módulos (`datos/kits.json`) |

Para ver el servidor de otro PC: arrancarlo con `--host 0.0.0.0` y abrir `http://<ip>:8000`.

## 5. Serie ESP32 ↔ PC (`captar/serial_bridge.py`)
ESP32 → PC, una línea JSON por segundo: `{"temp": 27.4, "humedad": 48.0, "luz": 0.6, ...}`
(claves = tipos de evento). PC → ESP32: `{"<destino>": <valor>}` + `\n`
(hoy `{"rele": true}`, `{"buzzer": 300}`; O1·B añade `claraboya`, `ac`, `nebulizador`, `ventilador`
en `CAMPOS`/`_payload` de `captar/serial_bridge.py` y en el firmware).

## 6. Propiedad de carpetas
| Carpeta / fichero | Dueño |
|---|---|
| `vision/`, `captar/`, `hardware/`, `web/caida.*`, `web/camara.html` | O1 |
| `control/`, `servidor/`, `sim/`, `nucleo/` (con PR `contrato:`), `web/index.html` | O2 |
| `web/gemelo.*`, `web/configurador.*`, `web/metricas.*`, `web/mapa.*`, `web/modelos/`, `pitch/`, `datos/kits.json`, `README.md` | O3 |
| `tests/test_<area>*.py` | dueño del área |
