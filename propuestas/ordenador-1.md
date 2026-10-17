# Propuestas escritas por la IA del Ordenador 1

Formato y reglas: AGENTS.md § Propuestas. Solo el Ordenador 1 crea propuestas aquí; el destinatario solo añade una línea `→ ON: aceptada/descartada porque …` debajo de cada bloque.

### [para O2] Alerta 061 solo con `desmayo`, no con `caida`
Problema: `control/reglas.py` dispara la alerta crítica con `caida is True`, así una caída de la
que la persona se levanta en 2 s ya avisa al 061 (falsa alarma). · Propuesta: `caida` → aviso
«persona en el suelo» (nivel aviso); solo `desmayo.activo` → crítico + `avisar()`; incluir
`desmayo.persona` y `aforo` en el mensaje. · Impacto en el jurado: menos falsos positivos =
creíble para el SEM. · Coste: S

### [para O3] Avatares desde `personas`
`personas` ya sale (sim y cámara) a 2 Hz: `{"id","x","y","etiqueta","estado"}` en metros, marco
refugio (x lateral, y fondo desde la cámara en el centro de la fachada de entrada). `estado` =
de_pie / sentado / suelo → postura del avatar; etiqueta flotante encima. Desmayo: avatar
`desmayo.persona` en rojo. · Coste: S
