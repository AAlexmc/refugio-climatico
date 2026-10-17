# Guion del pitch OASI — 3 minutos

Solo cifras marcadas ✅ en `pitch/cifras.md`. Lo que es cálculo propio se dice «estimado».
Antes de empezar: servidor arrancado, `/gemelo.html` abierto, cámara apuntando al suelo del refugio, móvil con `/mapa.html`.

| Tiempo | Bloque | Qué decir / hacer |
|---|---|---|
| 0:00–0:20 | **Gancho** | «**5.807 muertes atribuibles al calor en España este verano de 2026**; 1.952 en Cataluña. El 97 % tenía 65 años o más. Y el 8 de julio Barcelona marcó **40,5 °C**, récord histórico.» Pausa. «Esta gente no muere en la playa: muere en casa, o esperando el bus.» |
| 0:20–0:40 | **Problema** | «Barcelona tiene unos 500 refugios climáticos, y es un gran esfuerzo. Pero el 75 % son interiores con horario: bibliotecas, centros cívicos. Quien espera el bus a las 16 h a pleno sol, o el vecino de noche, no tiene un refugio *en la calle, abierto siempre y que sepa si estás bien*.» |
| 0:40–1:00 | **Solución OASI** | «OASI es un refugio climático **modular** que se monta en la calle. Cúpula clara de control solar que **no hace invernadero**, placas solares fuera en la corona, plantas dentro, **batería propia**. El control decide: ventilar primero, nebulizar solo si el aire es seco, aire acondicionado solo en el pico. Y una cámara cuenta personas y detecta desmayos **sin guardar ni una imagen**.» |
| 1:00–2:00 | **DEMO en vivo** | Ver pasos abajo. |
| 2:00–2:20 | **Coste** | «Una parada OASI de 2 módulos: 20 plazas, 1,6 kWp de placas, 5 kWh de batería, **unos 13.400 € de materiales (estimado)**. Una terraza privada de 1 módulo, unos 7.600 €; una comunitaria de 6 módulos, unos 38.400 €.» |
| 2:20–2:40 | **Modelo de negocio y escalado** | «Tres clientes: Ajuntament y TMB (venta o concesión con publicidad en la marquesina), comunidades y plazas (alquiler de temporada, junio–septiembre), bares y particulares (venta + mantenimiento). Barcelona tiene unas **2.590 paradas (dato sin verificar)**: cada marquesina es un refugio en potencia.» |
| 2:40–3:00 | **Cierre** | «Sevilla tiene paradas bioclimáticas piloto; nadie junta **modular + autónomo con el sol + control que decide + vigila la salud**. OASI: un refugio en cada parada, abierto siempre, y que sabe si estás bien. Gracias.» (Enseñar QR a `/mapa.html`.) |

## DEMO en vivo (1:00–2:00), paso a paso

1. **`/gemelo.html` (0:15)** — «Este es el gemelo digital de nuestro refugio.» Ola de calor simulada: fuera sube, dentro se mantiene; señalar claraboya, AC y niebla cuando reaccionan.
2. **`/camara.html` (0:20)** — Cámara real: «cuenta personas, solo etiquetas y esqueletos». **Alguien se tumba en el suelo** → se enciende la **alerta 061** en el panel. «Ningún vídeo sale del ordenador del refugio.»
3. **`/metricas.html` (0:10)** — °C ganados frente a la calle, kWh solares, autonomía de la batería, €/día y CO₂. Decir «datos de la simulación».
4. **`/configurador.html` (0:10)** — Cambiar de «parada de bus» a «terraza comunitaria», añadir módulos: cambian aforo, placas, batería y coste.
5. **`/mapa.html` (0:05)** — En el móvil: «el ciudadano ve dónde hay sitio». Pulsar «El más cercano con sitio». Aclarar: **R1 (Pl. Catalunya) es en vivo; los otros 5 son simulados**.

Resolver el desmayo en el panel (`Resolver desmayo`) para dejar el sistema limpio.

## Plan B si falla la cámara

- En el panel (`/`, pestaña Panel) pulsar **«Simular desmayo»** → mismo evento `desmayo`, misma alerta 061 y mismo aviso en `/mapa.html`. Decir: «la cámara es una fuente más; aquí inyectamos el mismo evento».
- Aforo: botón **«Simular lleno (25)»** para ver el cambio a «lleno» en el mapa.
- Si cae también el servidor: capturas de `pitch/` y el gemelo se explica en voz. No improvisar cifras.
- Wifi: todo corre offline en local; si el móvil no conecta, enseñar `/mapa.html` en el portátil.

## Preguntas probables del jurado

- **¿Privacidad? ¿Grabáis a la gente?** No. La imagen no sale de la RAM del PC del refugio; solo se guardan números, etiquetas y esqueletos. Sin caras, sin vídeo.
- **¿No es un invernadero?** No: cubierta de control solar (factor solar 0,29–0,35 frente a 0,88 del vidrio normal, **3 veces menos calor solar**), placas FV en la corona que dan sombra, claraboya motorizada que ventila primero y plantas que enfrían por evapotranspiración.
- **¿Cuánto cuesta?** Estimado: ~13.400 € de materiales una parada de 2 módulos. Es cálculo propio, no presupuesto; el coste de una marquesina actual de Barcelona no lo tenemos con fuente.
- **¿Mantenimiento de plantas y agua?** Plantas resistentes de bajo riego en jardineras; la nebulización usa poca agua (alrededor de 4 L/h por boquilla, estimado, y solo se activa con aire seco). Mantenimiento incluido en el contrato de venta/concesión; en terrazas privadas lo asume el titular. Pendiente de validar en piloto.
- **¿Y la humedad en Barcelona?** Es alta, por eso **nebulizamos solo con humedad < 60 %**: humidificar con aire húmedo sube el índice de calor. El control decide con el índice de calor NOAA, no solo con la temperatura. En días húmedos manda la ventilación y la sombra.
- **¿Y si no hay sol o red?** Batería con reserva mínima para control y alerta médica aunque no haya sol ni red.
- **¿Es real o simulado?** Cámara, control y panel funcionan de verdad; el clima y la energía son simulados con el mismo contrato que los sensores. En el mapa solo R1 es en vivo. Lo medido de verdad lo haremos con la maqueta.
