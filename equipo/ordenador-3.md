# Ordenador 3 — Gemelo 3D + configurador + Métricas + app ciudadana + pitch (2 personas)

Persona A: 3D (gemelo + configurador). Persona B: producto (cifras, kits, pestaña Métricas,
mapa ciudadano, pitch). Es lo que el jurado VE y lo que lo convence.

Orden de trabajo de la IA: 3A·H1 → 3B·H1 (cifras + `datos/kits.json`) → 3B·H2 (pestaña Métricas)
→ 3A·H2 (configurador) → 3B·H3 (mapa + pitch) → 3A·H3.

## 3A · Gemelo 3D + configurador modular
**Misión**: lo que el jurado VE. Un refugio 3D vivo que reacciona a los eventos, y un
configurador para montar el kit (parada de bus / terraza comunitaria / terraza privada)
añadiendo o quitando módulos.

Ya tienes: Three.js vendorizado en `web/vendor/` (`three.module.js`, `controls/OrbitControls.js`,
loaders GLTF…). Sin CDN (wifi del evento). Eventos por `ws://<host>/ws` (ver `web/index.html`).

### Hito 1 (≤ 1,5 h): `web/gemelo.html` + `web/gemelo.js`
- Módulo base procedural (sin modelos externos): planta hexagonal o rectangular, estructura,
  **cúpula transparente** (MeshPhysicalMaterial con transmission), **placas FV fuera en la corona**,
  claraboya que se abre/cierra animada (`claraboya` 0..1), bancos, jardineras con plantas.
- Reacciona a: `claraboya`, `ac` (partículas/flujo azul), `nebulizador` (niebla), `temp` (tinte),
  `aforo`/`personas` (avatares simples en sus posiciones x,z), `alerta desmayo` (avatar rojo + pulso),
  `solar`/`bateria` (indicador en las placas).
- Enlazar desde la cabecera de `web/index.html` (pide a O2 o PR mínimo).

### Hito 2: configurador (`web/configurador.html`)
- Elegir kit → layout por defecto; botones + / − módulo; los módulos se acoplan por los laterales.
- Al cambiar: publica `modulos` `{"kit","n","area_m2"}` vía `POST /api/evento` → el simulador
  de O2 recalcula. Mostrar aforo máximo, m² FV, kWh batería y coste (de `datos/kits.json`, 3B).

### Hito 3: modo presentación
- Cámara orbitando, cortes día/noche (sol moviéndose según la hora simulada), captura para slides.

## 3B · Producto, pestaña Métricas, app ciudadana y pitch
**Misión**: convertir la técnica en un proyecto ganador: números con fuente, coste, modelo de
negocio, la **pestaña de Métricas**, el mapa ciudadano y el pitch.

### Hito 1 (≤ 1 h): cifras y kits
- `pitch/cifras.md`: cifras CON FUENTE (URL): muertes por calor en BCN/Cataluña, red actual de
  «refugis climàtics» del Ajuntament (cuántos, horario, distancia media), temperatura en paradas de
  bus al sol, coste de una marquesina actual.
- `datos/kits.json`: para cada kit (`parada_bus`, `terraza_comunitaria`, `terraza_privada`):
  módulos por defecto, m², aforo máx., m² FV, kWh batería, coste materiales (€), precio venta/alquiler.
  Materiales de cúpula comparados (vidrio control solar, ETFE, policarbonato): g, U, €/m², fuente.

### Hito 2: pestaña Métricas (`web/metricas.html`)
- Consume `GET /api/metricas` (lo crea O2; mientras, usa un JSON de ejemplo con LA MISMA forma
  marcado «datos de ejemplo»). Gráfico 24 h: calle vs dentro, solar vs consumo, batería.
  Tarjetas: °C reducidos, horas de riesgo evitadas, kWh solares, autonomía, €/día, CO₂.
- Gráficos sin CDN: SVG/canvas propio o librería vendorizada en `web/vendor/`.
- Enlazar desde la cabecera de `web/index.html`.

### Hito 3: app ciudadana (`web/mapa.html`) + pitch
- Mapa (SVG de Barcelona o tiles offline) con refugios: temp dentro, aforo, «hay sitio / lleno»,
  ruta al más cercano. Móvil primero.
- `pitch/guion.md`: 3 min — usuario → problema con número → OASI → demo → coste → escalado
  (Ajuntament, TMB marquesinas, bares/terrazas, comunidades de vecinos) → impacto.
- Modelo de negocio: venta a ayuntamiento / alquiler por temporada / patrocinio en marquesina.

## Extras O3 (cuando H1–H3 estén)
- **Comparador de materiales** en el configurador: elegir vidrio / ETFE / policarbonato y ver
  cómo cambia la temperatura (llama a la sim de O2) → demuestra «sin efecto invernadero».
- **Vista noche**: placas FV sin sol, batería bajando, luz cálida interior.
- **QR en la marquesina** → `mapa.html` en el móvil del jurado durante el pitch.
- **Slides** (`pitch/`) con capturas del gemelo, la cámara con etiquetas (sin caras) y la pestaña Métricas.
- **Escalado**: cuántos OASI cubren Barcelona a < 5 min a pie de cualquier parada (cálculo + mapa).
- **Accesibilidad**: textos grandes, contraste, catalán/español/inglés en la app ciudadana.

## Estado
- 17-10 ~15:30 · **EN CURSO desde el Ordenador 1 (Claude)**: 3A·H1 gemelo 3D + 3A·H2 configurador,
  3B·H1 cifras + `datos/kits.json`, 3B·H2 pestaña Métricas. **Gemini (O3): empieza por 3B·H3
  (`web/mapa.html` + `pitch/guion.md`) y los Extras O3**; revisa los PRs `o3/*` que vayan entrando.
