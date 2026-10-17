# OASI — refugio climático modular

## Problema
Olas de calor cada vez más largas en Barcelona. La gente vulnerable (mayores, niños, personas
sin aire acondicionado en casa, quien espera el bus a pleno sol) no tiene dónde refugiarse a
menos de 5 min a pie. Los «refugis climàtics» actuales son edificios (bibliotecas, escuelas)
con horario y sitio fijo.

## Solución
**OASI**: refugio climático **modular** que se monta en la calle y se adapta al sitio.

- **Módulos acoplables** (crecer/reducir): se unen por los laterales; mismo kit de uniones.
- **3 kits**: `parada_bus` (2–3 módulos, lineal), `terraza_comunitaria` (4–8, plaza/azotea
  de vecinos), `terraza_privada` (1–2, bar/restaurante/particular).
- **Cúpula clara que NO hace invernadero**: vidrio/ETFE de control solar (deja pasar luz visible,
  bloquea IR), serigrafiado (frit) en la zona alta, y **placas fotovoltaicas fuera, en la corona**
  que además dan sombra. Plantas dentro (sombra + evapotranspiración + bienestar).
- **Energía propia**: placas FV → **batería** → AC, nebulización, ventiladores, sensores, luz.
  Reserva mínima de batería para control + alerta médica aunque no haya sol ni red.
- **Clima automático**: claraboya motorizada (ventilación natural primero), aire acondicionado,
  nebulización/humidificación evaporativa cuando hay mucha gente y el aire es seco.
- **Visión artificial (RealSense D435i)**: cuenta personas con etiquetas (aforo) y detecta
  desmayos (persona en el suelo sin moverse) → **alerta al servicio médico (061 SEM)**.
  **No se guardan fotos**: solo números, etiquetas y esqueletos.
- **Panel + app ciudadana**: mapa de refugios con temperatura dentro, aforo y si hay sitio.
- **Métricas**: °C ganados vs calle, horas de confort, kWh solares, autonomía de batería, € y CO₂.

## Decisiones de diseño (defendibles ante el jurado)
1. **Ventilar antes que enfriar**: si fuera está más fresco (< 27 °C) se abre la claraboya y el AC
   se apaga. Con 35 °C fuera, abrir solo mete calor.
2. **Nebulizar solo con HR < 60 %**: en Barcelona la humedad es alta; humidificar con aire húmedo
   SUBE el índice de calor. El control lo decide con el índice de calor NOAA, no solo con la temperatura.
3. **Privacidad por diseño**: la imagen no sale de la RAM del ordenador del refugio.
4. **Todo funciona sin hardware** (simulador con el mismo contrato que los sensores reales).

## Demo (3 min de pitch)
1. Configurador 3D: elegir kit «parada de bus», añadir módulos → cambia aforo, coste, placas.
2. Ola de calor simulada: fuera 36 °C, dentro baja; claraboya se cierra, AC on con energía solar.
3. Llega un bus (aforo sube) → nebulizador / AC más fuerte; cámara real cuenta personas.
4. Alguien se tumba en el suelo frente a la RealSense → alerta 061 en el panel y en el móvil.
5. Pestaña Métricas: °C reducidos, horas de riesgo evitadas, kWh solares, € por refugio.
6. Maqueta física (ESP32): servo abre la claraboya, ventilador y LED reaccionan en vivo.
