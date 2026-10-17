# esp32_refugio (ESP32-S3 N16R8, ESP-IDF v6.1)

Publica cada 1 s una línea JSON por USB (`/dev/ttyACM0`) y acepta comandos.
Protocolo: `docs/contratos.md`. Cada sensor se activa/desactiva y se recoloca
en `idf.py menuconfig` -> "Hospital sensor"; el deshabilitado no sale en el JSON.

## Cableado (por defecto)

**Los GPIO del ESP32-S3 son de 3,3 V, no tolerantes a 5 V.** Alimenta de 3,3 V
o usa divisor/adaptador de nivel en cualquier salida de 5 V hacia el ESP32.

| Sensor | GPIO | Notas |
|---|---|---|
| DHT11/DHT22 | 4 | Datos. VCC 3,3 V. Pull-up interno activado; con cable largo añade 4,7 kΩ a 3,3 V. Modelo en menuconfig |
| LDR | 1 (ADC1) | Divisor: 3,3 V - LDR - GPIO1 - 10 kΩ - GND. Normalizado 0..1; si va al revés, "Invertir" |
| PIR | 5 | Salida digital. Si el PIR es de 5 V (HC-SR501), alimenta a 5 V pero la salida (3,3 V) ya vale; verifica con multímetro. Si saca 5 V, divisor 10k/20k |
| Relé | 6 | Señal IN. Módulo de 5 V que no active con 3,3 V: transistor o módulo con optoacoplador. "Activo bajo" en menuconfig |
| Buzzer | 7 | Activo: GPIO alto = suena. Pasivo: tono PWM (LEDC). Buzzers grandes: vía transistor |

Evitados a propósito: 0/3/45/46 (strapping), 19/20 (USB), 26-37 (flash/PSRAM octal).

## Flashear

```bash
source ~/esp/v6.1/esp-idf/export.sh
cd captar/esp32_refugio
idf.py set-target esp32s3     # una vez
idf.py menuconfig             # opcional: pines / sensores
idf.py -p /dev/ttyACM0 flash monitor
```

Usa el USB nativo (puerto "USB" de la placa, no el UART). Si no entra en modo
descarga: mantener BOOT, pulsar RESET. Cierra el monitor antes de arrancar el
servidor (un solo lector del puerto).

## Probar con el servidor

```bash
python -m servidor.app --clima esp32
```

Prueba manual de comandos: `echo '{"rele":true}' > /dev/ttyACM0` (el servidor
no debe estar corriendo).
