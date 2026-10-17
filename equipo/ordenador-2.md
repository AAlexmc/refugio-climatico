# Ordenador 2 — Control + servidor + simulador térmico/energía (2 personas)

Persona A: control, servidor, alertas, integración. Persona B: simulador físico, energía
(placas FV + batería) y backend de métricas. Eres quien integra: mergea con frecuencia,
arranca la demo final y mantiene `main` siempre funcionando.

Orden de trabajo de la IA: 2A·H1 → 2B·H1 → 2B·H2 (`/api/metricas`, lo espera O3) → 2A·H2 → 2A·H3 → 2B·H3.

## 2A · Control, servidor e integración
**Misión**: el cerebro. Reglas de clima y emergencias, servidor, panel de integración,
y que las piezas de los demás encajen (eres quien mergea con más frecuencia y arranca la demo).

Ya tienes: `servidor/app.py` (FastAPI + WS + bus), `control/reglas.py` (reglas base con tests en
`tests/test_refugio.py`), `control/alerta_medica.py` (log + webhook), `web/index.html` (panel mínimo).

### Hito 1 (≤ 1 h): control serio
- Publicar `indice_calor` calculado.
- Reglas nuevas: `bateria_baja` (< 20 % → modo ahorro: AC a consigna más alta, prioridad a
  ventilación/nebulización), `calor` (índice de calor dentro > 32 °C = aviso), CO₂ alto → abrir claraboya.
- Modo **ahorro solar**: si sobra sol y batería > 90 %, preenfriar (consigna 1 °C más baja).
- Claraboya con apertura parcial (0.3/0.6/1.0), no solo todo/nada.
- Tests de cada regla (entrada → comando/alerta exacta).

### Hito 2: alerta médica de verdad (demo)
- `OASI_WEBHOOK` → notificación al móvil (ntfy.sh o bot de Telegram). Mensaje con refugio,
  hora, ubicación (lat/lon del refugio) y nº de personas dentro.
- Botón «Atendido» en el panel → resuelve la alerta.
- Recordatorio: la demo NUNCA llama al 061 real.

### Hito 3: demo guiada + multi-refugio
- `POST /api/demo` que ejecute el guion de `docs/reto.md` § Demo (ola de calor → bus llega →
  desmayo → métricas) con eventos `guion` que el panel muestra.
- Varios refugios simulados (`R1..R5`) para el mapa de O3.

## 2B · Simulador térmico + energía + métricas (backend)
**Misión**: demostrar con números que OASI funciona: °C dentro vs calle, energía solar,
batería, coste. Es lo que convence al jurado.

Ya tienes: `sim/clima.py` (modelo base de 1 nodo, placas FV fuera en la corona + batería, obedece
comandos), `sim/aforo_sim.py`, y `sim/referencia/modelo_habitacion.py` (modelo RC de 2 nodos
del proyecto anterior: ola de calor Barcelona, COP variable, precio luz, métricas) para reutilizar.

### Hito 1 (≤ 1,5 h): `sim/termico.py`
- Modelo RC 2 nodos del refugio (aire + masa: suelo/jardineras con tierra húmeda), parametrizado
  por **kit y nº de módulos** (área, volumen, m² de cúpula, m² FV, kWh batería).
- Materiales comparables: vidrio simple / vidrio control solar / ETFE serigrafiado / policarbonato
  (factor solar g, U). Mostrar que el «invernadero» desaparece con control solar + FV en corona + plantas.
- Personas 100 W sensibles + vapor; AC con COP que cae con la temperatura; nebulización con
  eficiencia según HR; ventilación natural según apertura de claraboya.
- `FuenteTermicaSim` con el mismo contrato que `sim/clima.py` → registrar como `sim` en
  `nucleo/fuente.py` (PR `contrato:` si cambias el registro).

### Hito 2: `GET /api/metricas` (la pestaña la pinta O3)
- `sim/metricas.py`: escenario 5 días de ola de calor, 3 políticas: **calle sin refugio** /
  **cúpula sin control** / **OASI**. Devuelve JSON:
  `{"series": {"t": [...], "temp_calle": [...], "temp_oasi": [...], "bateria": [...], "solar": [...]},
    "resumen": {"grados_reducidos_pico", "horas_riesgo_evitadas", "kwh_solares", "autonomia_h",
    "pct_autoconsumo", "coste_eur_dia", "co2_kg_evitado"}}`
- Añadir la ruta en `servidor/app.py` (2A revisa).
- Datos: temperatura horaria real de una ola de calor en BCN (AEMET/Meteocat) en `sim/data/`.

### Hito 3: dimensionado
- Para cada kit: cuántas placas y kWh de batería para 100 % autonomía en el día tipo → tabla
  en `datos/kits.json` (coordina con O3).

### Extra 2B: energía solar y batería
- Placas FV montadas FUERA, en la corona de la cúpula (también dan sombra) → batería LiFePO4.
  Hoy en `sim/clima.py` (`AREA_FV`, `EF_FV`, `BAT_KWH`, `BAT_RESERVA`); llévalo a `sim/termico.py`
  y escálalo con los módulos del kit. Eventos `solar` (W), `bateria` (%), `red` (W importados).
- Métrica estrella: «% de horas de ola de calor cubiertas solo con sol + batería».

## Extras O2 (cuando H1–H3 estén)
- **Predictivo**: con la previsión de temperatura de mañana, preenfriar la masa térmica de madrugada
  (ventilación nocturna gratis) y cargar batería; métrica «kWh ahorrados por anticipar».
- **Lluvia/viento**: cerrar claraboya con viento > 10 m/s (seguridad estructural).
- **Mantenimiento**: riego de plantas según humedad de tierra; aviso de filtro del AC.
- **Persistencia**: guardar series agregadas (no personas) en `datos/historico.csv` para métricas reales.
- **API pública** `GET /api/refugios` (id, lat/lon, temp, aforo, plazas libres) para el mapa de O3.
- **Tests de lazo cerrado**: 24 h simuladas con la política OASI nunca superan índice de calor 32 °C
  con aforo < máx. (si falla, el dimensionado de 2B está mal).

## Estado
- (actualiza aquí al cerrar cada hito)
