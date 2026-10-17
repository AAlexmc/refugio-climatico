// Entrenar caída: estado en vivo (/api/caida/vivo) + grabar de pie / suelo + calcular + guardar.
'use strict';
const $ = (id) => document.getElementById(id);
const ETQ = { de_pie: 'DE PIE', suelo: 'EN EL SUELO', caida: 'CAÍDA', sin_persona: 'SIN PERSONA' };
const med = { de_pie: null, suelo: null };
let calculado = null;          // umbrales calculados, pendientes de guardar

async function api(ruta, metodo = 'GET', cuerpo) {
  const r = await fetch(ruta, {
    method: metodo,
    headers: cuerpo ? { 'Content-Type': 'application/json' } : undefined,
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  });
  let d = null;
  try { d = await r.json(); } catch (e) { /* sin cuerpo */ }
  if (!r.ok) throw new Error((d && d.detail) || `error ${r.status}`);
  return d;
}

const fmt = (x, n = 2) => (x == null ? '—' : Number(x).toFixed(n));
function error(e) { $('err').textContent = e ? (e.message || String(e)) : ''; }

function pintarUmbrales(u) {
  $('u-suelo').textContent = `${fmt(u.cadera_suelo)} m`;
  $('u-alto').textContent = `${fmt(u.cadera_levantado)} m`;
  $('u-ang').textContent = u.angulo_torso == null ? 'desactivado (decide solo la cadera)' : `${fmt(u.angulo_torso, 0)}°`;
  $('u-desc').textContent = u.exigir_descenso ? 'sí' : 'no (modo demo)';
}
// El checkbox lo manda el usuario: solo se repinta al cargar y tras guardar/borrar (no en el poll de vivo()).
function pintarDemo(u) { $('demo').checked = !u.exigir_descenso; }

async function cargarDemo() {
  try { pintarDemo((await api('/api/caida/calibracion')).umbrales); } catch (e) { /* sin servidor */ }
}

async function vivo() {
  try {
    const v = await api('/api/caida/vivo');
    const est = v.edad_s != null && v.edad_s > 3 ? 'sin_persona' : v.estado;
    $('estado').textContent = ETQ[est] || est;
    $('estado').className = est;
    $('v-cadera').textContent = fmt(v.visible ? v.cadera_z : null);
    $('v-angulo').textContent = fmt(v.visible ? v.angulo : null, 0);
    $('v-edad').textContent = fmt(v.edad_s, 1);
    pintarUmbrales(v.umbrales);
    $('b-pie').disabled = $('b-suelo').disabled = v.grabando;
  } catch (e) {
    $('estado').textContent = 'SIN CÁMARA (arranca con --pose realsense|webcam)';
    $('estado').className = 'sin_persona';
  }
}

async function modo() {
  try {
    const m = await api('/api/pose/modo');
    $('modo').textContent = 'Refugio del gemelo: '
      + (m.modo === 'sim' ? 'simulación' : m.modo === 'camara' ? 'cámara' : 'ninguno');
    const aviso = $('msg-modo');
    aviso.hidden = !(m.conmutable && m.modo === 'sim');
    aviso.textContent = 'El gemelo usa la simulación: la caída detectada aquí no llega al robot. '
      + 'Cambia a «Cámara» en el panel para verla en el gemelo (grabar y calcular funcionan igual).';
  } catch (e) { /* servidor caído: lo cubre vivo() */ }
}

async function grabar(clase) {
  error(null);
  const b = $(clase === 'de_pie' ? 'b-pie' : 'b-suelo');
  const r = $(clase === 'de_pie' ? 'r-pie' : 'r-suelo');
  b.disabled = true; r.textContent = ' grabando 3 s…';
  try {
    const d = await api('/api/caida/grabar', 'POST', { clase, segundos: 3 });
    med[clase] = { cadera_z: d.cadera_z, angulo: d.angulo };
    r.textContent = ` ${d.muestras} muestras · cadera ${fmt(d.cadera_z)} m · torso ${fmt(d.angulo, 0)}°`;
  } catch (e) { med[clase] = null; r.textContent = ''; error(e); }
  b.disabled = false;
  $('b-calc').disabled = !(med.de_pie && med.suelo);
  calculado = null; $('b-guardar').disabled = true;
}

async function calcular() {
  error(null);
  try {
    const d = await api('/api/caida/calcular', 'POST',
      { pie: med.de_pie, suelo: med.suelo, exigir_descenso: !$('demo').checked });
    calculado = d.umbrales;
    $('calc').textContent = `Calculado: suelo < ${fmt(d.umbrales.cadera_suelo)} m, levantado > ${fmt(d.umbrales.cadera_levantado)} m`;
    $('nota').textContent = d.nota;
    $('b-guardar').disabled = false;
  } catch (e) { calculado = null; $('calc').textContent = ''; $('nota').textContent = ''; error(e); }
}

async function guardar() {
  error(null);
  try {
    const base = calculado || (await api('/api/caida/calibracion')).umbrales;
    const u = { ...base, exigir_descenso: !$('demo').checked };
    const r = await api('/api/caida/calibracion', 'POST', u);
    pintarDemo(r.umbrales);
    $('calc').textContent = 'Guardado y aplicado en caliente.';
    $('b-guardar').disabled = true; calculado = null;
  } catch (e) { error(e); }
}

async function defecto() {
  error(null);
  try {
    const r = await api('/api/caida/calibracion', 'DELETE');
    pintarDemo(r.umbrales);
    $('calc').textContent = 'Valores por defecto restaurados.'; $('nota').textContent = '';
  } catch (e) { error(e); }
}

$('b-pie').addEventListener('click', () => grabar('de_pie'));
$('b-suelo').addEventListener('click', () => grabar('suelo'));
$('b-calc').addEventListener('click', calcular);
$('b-guardar').addEventListener('click', guardar);
$('b-defecto').addEventListener('click', defecto);

const img = $('cam');
img.addEventListener('error', () => {
  img.hidden = true; $('aviso').hidden = false;
  setTimeout(() => { img.hidden = false; $('aviso').hidden = true; img.src = 'camara.mjpg?' + Date.now(); }, 3000);
});

cargarDemo();
setInterval(vivo, 300); vivo();
setInterval(modo, 1500); modo();
