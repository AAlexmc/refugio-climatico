# Ordenador 1 — Visión artificial + maqueta física (2 personas)

Persona A: visión (RealSense). Persona B: maqueta + ESP32. La IA alterna entre las dos
partes; empieza por **1A Hito 1** y lanza **1B Hito 1** en paralelo (subagente/otra terminal si puede).

Orden de trabajo de la IA: 1A·H1 → 1B·H1 → 1A·H2 → 1B·H2 → 1A·H3 → 1B·H3.

## 1A · Visión (RealSense D435i)
**Misión**: con UNA RealSense, contar personas con etiquetas (aforo) y detectar desmayos.
Privacidad: **nunca se guardan fotos ni vídeo** (solo números, etiquetas, posiciones, esqueleto).

Ya tienes (reutilizado del proyecto anterior, con tests):
- `vision/pose.py` — `FuentePose`: RealSense/webcam + MediaPipe 3D → `pose`, `caida`.
- `vision/caidas.py`, `vision/calibracion.py` — detector de caída con umbrales entrenables
  (`/caida.html`: grabar «de pie» y «suelo» con tu cuerpo).
- `vision/modo_pose.py` — conmutador cámara/simulación con auto-respaldo.
- `vision/vista.py` + `/camara.html` — imagen en directo con esqueleto (solo RAM).
- `vision/aforo.py` — STUB con el contrato de `aforo`/`personas`.

### Hito 1 (≤ 1 h): aforo real
- `vision/aforo.py`: ultralytics YOLO (clase person) + `model.track(persist=True, tracker="bytetrack.yaml")`
  sobre el color de la RealSense; profundidad alineada → (x, z) en metros de cada persona.
- Publica `aforo` (int) y `personas` (`[{"id", "x", "z", "etiqueta": "Persona 3"}]`) ~1 Hz.
- Con `--ver-camara`, cajas + etiqueta dibujadas en `/camara.mjpg` (sin escribir a disco).
- Una sola RealSense para pose + aforo: abrir el pipeline UNA vez y repartir frames
  (no dos `rs.pipeline()` sobre el mismo dispositivo).
- Test: `tests/test_vision_aforo.py` con un detector falso (sin cámara en CI).

### Hito 2: desmayo
- Desmayo = `caida` + inmóvil ≥ N s (cadera casi quieta). Publica `desmayo`
  `{"activo", "segundos_inmovil", "zona"}`. El control (O2) dispara la alerta 061.
- Con varias personas: el desmayo va asociado al id de la etiqueta.

### Hito 3: robustez demo
- Imagen cortada (piernas fuera de cuadro) — pendiente del proyecto anterior.
- Ensayar con 3–4 compañeros delante; ajustar umbrales en `/caida.html`.
- Dejar `--pose realsense --aforo yolo --ver-camara` como arranque de la demo.

### Entregable para el pitch
Vídeo/captura de `/camara.html` con cajas «Persona 1..n» y el panel mostrando aforo + alerta.

## 1B · Maqueta + ESP32
**Misión**: una maqueta pequeña del refugio que se mueve de verdad: servo de claraboya,
ventilador, LED (AC / nebulizador / alerta), sensor de temperatura y humedad. Si no hay
hardware, la parte de firmware + puente igualmente queda lista y probada.

Ya tienes: `captar/esp32_refugio/` (firmware ESP-IDF v6.1 para ESP32-S3: DHT, LDR, PIR, relé,
buzzer, protocolo JSON por USB — ver su README) y `captar/serial_bridge.py` (puente serie → bus, con tests).

### Hito 1 (≤ 1 h): inventario + protocolo
- Lista en «Estado» el hardware real disponible del equipo (placa, sensores, servo, relés, LED, ventilador).
- Ampliar `serial_bridge.py`: comandos `claraboya` (0..1 → ángulo servo), `ac`, `nebulizador`,
  `ventilador`; lecturas `claraboya`, `ac`… de vuelta. Tests con puerto falso (ya hay patrón).

### Hito 2: firmware
- Servo por LEDC PWM (50 Hz), LED RGB/tira: azul = AC, blanco = nebulizador, rojo parpadeo = desmayo.
- Renombrar proyecto `hospital_sensor` → `refugio_sensor`. Compilar: `idf.py build`.
- Si no hay ESP-IDF a mano: versión Arduino IDE en `captar/arduino_refugio/` con el MISMO protocolo.

### Hito 3: maqueta
- Cúpula con botella/cúpula de plástico transparente, base cartón pluma, «placas» en la corona.
- Fotos de la maqueta en `pitch/img/` (sin personas).
- Mini-humidificador USB por relé = nebulizador real en la demo.

### Extra 1B: sensores en la maqueta = refugio real
- Con la maqueta conectada, el servidor de demo se arranca con `--clima esp32`: el panel y el
  gemelo muestran la temperatura REAL de la maqueta (calentar con la mano/secador en el pitch).

## Extras O1 (cuando H1–H3 estén)
- **Zonas** en la imagen (banco, entrada, jardinera): aforo por zona y «zona del desmayo» en la alerta.
- **Mapa de calor de ocupación** agregado (sin imágenes) → evento para que O3 lo pinte en el gemelo.
- **Golpe de calor precoz**: persona sentada inmóvil mucho rato + índice de calor alto → aviso suave.
- **Botón físico SOS** en la maqueta (ESP32) → misma alerta que el desmayo.
- **Rendimiento**: YOLO en GPU (RTX), medir FPS y latencia caída→alerta (cifra para el pitch: «< 3 s»).
- **Anonimizado visible**: en `/camara.html` difuminar caras por defecto (demuestra la privacidad).

## Estado
- (actualiza aquí al cerrar cada hito)
