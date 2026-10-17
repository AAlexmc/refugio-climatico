# Maqueta OASI (escala ~1:20)

## Material
| Pieza | Qué usar | Para |
|---|---|---|
| Base | cartón pluma 30×20 cm | suelo del refugio (2 módulos acoplados) |
| Cúpula | media esfera / bol de PET transparente o botella de 5 L cortada | cúpula clara |
| Placas FV | cartulina negra con rejilla blanca (o mini-panel 5 V real) en la CORONA, por fuera | energía + sombra |
| Claraboya | tapa recortada en lo alto + bisagra de cinta + servo SG90 con varilla (clip) | ventilación |
| Plantas | musgo/plantitas de plástico en jardineras | sombra y realismo |
| Bancos y personitas | palillos / figuras | escala |
| Electrónica | ESP32-S3, DHT11/22, servo SG90, 3 LED (azul, blanco, rojo) + 220 Ω, relé, mini-humidificador USB, ventilador 5 V + transistor | ver `captar/esp32_refugio/README.md` |

## Montaje
1. DHT DENTRO de la cúpula (a media altura, sin sol directo).
2. Servo pegado bajo la corona; la varilla empuja la claraboya. Calibrar ángulos en `idf.py menuconfig`.
3. LED azul = AC, LED blanco o humidificador real = nebulizador, ventilador en un lateral.
4. LED rojo visible desde el público (alerta de desmayo).
5. Cables por debajo de la base; ESP32 al PC por el puerto USB nativo.

## Demo
- `python -m servidor.app --clima esp32 --pose realsense --ver-camara`
- Calentar con la mano / secador → temperatura sube → se cierra la claraboya + LED azul.
- Alguien se tumba delante de la RealSense → LED rojo parpadea + pitido + alerta en el panel.
- Sin fotos de personas en `pitch/img/`: solo la maqueta.
