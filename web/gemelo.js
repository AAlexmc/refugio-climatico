// Gemelo 3D del Pabellón Venturi (arriba) + métricas del día (abajo), con barra arrastrable.
// Eventos en vivo por WebSocket (docs/contratos.md); física del aire en el evento `fisica`.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { construirRefugio } from './oasi3d.js';
import { construirEntorno, posicionSol } from './entorno.js';

const Q = new URLSearchParams(location.search);
const REFUGIO = Q.get('refugio') || 'R1';
const $ = id => document.getElementById(id);
const LARGOS = [4, 6, 8, 10, 12], ANCHOS = [2.4, 3.6, 4.8];

// ---------------- escena ----------------
const arriba = $('arriba');
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
arriba.prepend(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x9ec9e6);
scene.fog = new THREE.Fog(0x9ec9e6, 25, 70);
const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 300);
const controls = new OrbitControls(camera, renderer.domElement);
controls.maxPolarAngle = Math.PI * 0.49; controls.enableDamping = true;
const hemi = new THREE.HemisphereLight(0xffffff, 0x556655, 0.9); scene.add(hemi);
scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
const sol = new THREE.DirectionalLight(0xfff2d8, 2); scene.add(sol, sol.target);
sol.castShadow = true; sol.shadow.mapSize.set(2048, 2048); sol.shadow.bias = -0.0005;
Object.assign(sol.shadow.camera, { left: -16, right: 16, top: 16, bottom: -16, near: 1, far: 60 });

// estado acumulado: se reaplica si el refugio se reconstruye
const E = { claraboya: 0, ac: false, nebulizador: false, ventilador: false, temp: null, solar: 0, bateria: 0, noche: false, fisica: null };
let temp_ext = null, aforo = null, personas = [], desmayo = { activo: false, persona: null };
let cfg = { largo: Number(Q.get('largo')) || 6, ancho: Number(Q.get('ancho')) || 2.4, lugar: Q.get('lugar') || 'bus' };
let refugio = null, entorno = null;

function construir(recolocar = true) {
  refugio?.dispose();
  if (!entorno || entorno.lugar !== cfg.lugar) { entorno?.dispose(); entorno = construirEntorno(scene, cfg.lugar); entorno.lugar = cfg.lugar; }
  refugio = construirRefugio(scene, { tipo: 'pabellon', largo: cfg.largo, ancho: cfg.ancho });
  refugio.set(E); refugio.setPersonas(personas); refugio.setDesmayo(desmayo);
  setTimeout(aplicarSol, 300);
  if (recolocar) {
    controls.target.copy(refugio.centro).setY(1.6);
    const d = Math.max(9, cfg.largo * 1.05 + cfg.ancho * 1.2);
    camera.position.set(refugio.centro.x + d * 0.75, d * 0.5, refugio.centro.z + d * 0.85);
  }
}

// ---------------- sol según la hora (Barcelona, julio) ----------------
let hora = Math.min(21, Math.max(6, new Date().getHours() + new Date().getMinutes() / 60));
let animando = false, tSombra = 0;
const cielo = new THREE.Color(), cDia = new THREE.Color(0x9ec9e6), cOcaso = new THREE.Color(0xf2b27a), cNoche = new THREE.Color(0x070b16);
const lBlanca = new THREE.Color(0xfff2d8), lNaranja = new THREE.Color(0xff9a4a);
function aplicarSol() {
  if (!refugio) return;
  const s = posicionSol(hora), e = s.elev, noche = e <= 0;
  E.noche = noche; refugio.set({ noche });
  const c = refugio.centro;
  sol.target.position.copy(c); sol.position.copy(c).addScaledVector(s.dir, 35);
  const f = Math.max(0, Math.sin(e * Math.PI / 180)), ocaso = Math.max(0, 1 - e / 15);
  sol.color.copy(lBlanca).lerp(lNaranja, noche ? 0 : ocaso); sol.intensity = noche ? 0 : 0.6 + 2.6 * f;
  hemi.intensity = noche ? 0.12 : 0.3 + 0.6 * f;
  cielo.copy(noche ? cNoche : cDia); if (!noche) cielo.lerp(cOcaso, ocaso * 0.7);
  scene.background.copy(cielo); scene.fog.color.copy(cielo);
  const ahora = performance.now();
  if (!animando || ahora - tSombra > 400) { tSombra = ahora; sombra(s); }
  marcarHora();
}
// % del suelo a la sombra: rayos desde una rejilla hacia el sol, solo contra mallas opacas y baratas
const rc = new THREE.Raycaster(), _p = new THREE.Vector3();
function sombra(s) {
  let txt = '—';
  if (s.elev > 0) {
    const L = refugio.limites, opacos = [];
    refugio.group.traverse(o => { if (o.isMesh && !o.isSkinnedMesh && !o.isInstancedMesh && !o.userData.compartido
      && !o.material.transparent && o.visible && (o.geometry.index?.count ?? o.geometry.attributes.position.count) < 20000) opacos.push(o); });
    let tot = 0, som = 0;
    for (let i = 0; i < 9; i++) for (let k = 0; k < 7; k++) {
      _p.set(L.minX + (i + 0.5) * (L.maxX - L.minX) / 9, 0.3, L.minZ + (k + 0.5) * (L.maxZ - L.minZ) / 7);
      rc.set(_p, s.dir); rc.far = 40; tot++;
      if (rc.intersectObjects(opacos, false).length) som++;
    }
    const pct = Math.round(100 * som / tot);
    txt = `${pct} % del suelo a la sombra · sol directo dentro ≈ ${Math.round(s.irr * (1 - pct / 100))} W/m²`;
  }
  $('s_hora').textContent = hhmm(hora);
  $('s_info').textContent = s.elev > 0 ? `Sol a ${Math.round(s.elev)}° · ${s.irr} W/m² · ${txt}` : 'Noche: sin sol (batería y luz cálida)';
}
const hhmm = h => { const hh = Math.floor(h), mm = Math.round((h - hh) * 60) % 60; return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`; };
$('s_rango').value = hora;
$('s_rango').oninput = e => { hora = Number(e.target.value); animando = false; $('s_play').textContent = '▶'; aplicarSol(); };
$('s_play').onclick = () => { animando = !animando; $('s_play').textContent = animando ? '❚❚' : '▶'; };

// ---------------- HUD ----------------
function hud() {
  const n = (v, u, d = 1) => v == null || Number.isNaN(+v) ? '—' : `${(+v).toFixed(d)}${u}`;
  const fz = E.fisica || {};
  $('h_ref').textContent = REFUGIO;
  $('h_temp').textContent = `${n(E.temp, '°')} / ${n(temp_ext, '°')}`;
  $('h_at').textContent = `${n(fz.t_aparente, '°')} / ${n(fz.t_aparente_ext, '°')}`;
  $('h_aforo').textContent = aforo ?? '—';
  $('h_bat').textContent = `${n(E.bateria, ' %', 0)} · ${n(E.solar, ' W', 0)}`;
  $('h_cla').textContent = Math.round(E.claraboya * 100) + ' % abierta';
  $('h_act').textContent = `${E.ac ? 'ON' : 'off'} · ${E.nebulizador ? 'ON' : 'off'} · ${E.ventilador ? 'ON' : 'off'}`;
  $('f_viento').textContent = n(fz.viento, ' m/s');
  // con la garganta cerrada no hay succión: se muestra la que habría (½·ρ·v²·(K²−1), K = 1,6)
  const pot = fz.viento == null ? null : 0.5 * 1.2 * fz.viento ** 2 * (1.6 ** 2 - 1);
  $('f_dpv').textContent = E.claraboya > 0 ? n(fz.dp_venturi, ' Pa') : (pot == null ? '—' : `cerrada (${pot.toFixed(1)} Pa)`);
  $('f_dps').textContent = n(fz.dp_chimenea, ' Pa', 2);
  $('f_q').textContent = fz.caudal_m3h == null ? '—' : `${Math.round(fz.caudal_m3h).toLocaleString('es-ES')} m³/h`;
  $('f_ach').textContent = n(fz.renovaciones_h, ' /h', 0);
  $('f_v').textContent = n(fz.v_ocupante, ' m/s', 2);
  $('f_ev').textContent = fz.evaporativo_w == null ? '—' : `${(fz.evaporativo_w / 1000).toFixed(1)} kW`;
  $('f_bh').textContent = n(fz.t_bulbo_humedo, ' °C');
}

// ---------------- eventos ----------------
const BOOL = new Set(['ac', 'nebulizador', 'ventilador']);
function evento(ev) {
  if (ev.tipo === 'guion') {
    const g = ev.valor || {}, el = $('guion');
    el.style.display = g.paso > 0 ? 'block' : 'none';
    if (g.paso > 0) el.textContent = `${g.paso}/${g.total} · ${g.titulo} — ${g.texto}`;
    return;
  }
  if (ev.refugio && ev.refugio !== REFUGIO) return;
  const v = ev.valor;
  switch (ev.tipo) {
    case 'claraboya': case 'ac': case 'nebulizador': case 'ventilador': case 'temp': case 'solar': case 'bateria':
      E[ev.tipo] = BOOL.has(ev.tipo) ? !!v : Number(v); refugio.set({ [ev.tipo]: E[ev.tipo] }); break;
    case 'fisica': E.fisica = v; refugio.set({ fisica: v }); break;
    case 'temp_ext': temp_ext = Number(v); break;
    case 'aforo': aforo = v; break;
    case 'personas': personas = Array.isArray(v) ? v : []; refugio.setPersonas(personas); break;
    case 'desmayo': desmayo = { activo: !!v?.activo, persona: v?.persona ?? null }; refugio.setDesmayo(desmayo); break;
    case 'alerta':
      if (v?.codigo === 'afluencia') { const on = v.nivel !== 'info'; $('afluencia').style.display = on ? 'block' : 'none'; if (on) $('afluencia').textContent = '👥 ' + v.mensaje; }
      if (v?.codigo === 'desmayo') { const on = v.nivel === 'critico'; $('banner').style.display = on ? 'block' : 'none'; if (on) $('banner').textContent = 'Alerta 061 · ' + (v.mensaje || 'desmayo'); }
      break;
    case 'modulos':
      if (v?.tipo === 'pabellon' && v.largo && v.ancho && (v.largo !== cfg.largo || v.ancho !== cfg.ancho)) { cfg = { ...cfg, largo: v.largo, ancho: v.ancho }; aplicarCfg(); }
      break;
  }
  hud();
}
function conectar() {
  const ws = new WebSocket(`ws://${location.host}/ws`), est = $('estado');
  ws.onopen = () => { est.textContent = 'en vivo'; est.className = 'ov'; };
  ws.onclose = () => { est.textContent = 'sin conexión'; est.className = 'ov off'; setTimeout(conectar, 1000); };
  ws.onerror = () => ws.close();
  ws.onmessage = m => { try { evento(JSON.parse(m.data)); } catch (e) { console.warn('evento ignorado', e); } };
}

// ---------------- configuración: ampliar a lo largo y a lo ancho ----------------
function info() {
  const L = cfg.largo, W = cfg.ancho, R = W / 2 + 0.15;
  const vol = L * W * 2.75 + L * Math.PI * R * R / 2, fv = 2 * 1.05 * (R + 0.03) * L * 0.9;
  $('c_largo').textContent = `${L} m`;
  document.querySelectorAll('#c_ancho button').forEach(b => b.classList.toggle('sel', Number(b.dataset.a) === W));
  $('c_info').textContent = `${(L * W).toFixed(1)} m² · ${Math.round(vol)} m³ · aforo ${Math.floor(L * W / 1.5)} · ` +
    `${Math.max(1, Math.round(L / 2))} extractores · FV ${(fv * 0.2).toFixed(1)} kWp · batería ${(2.5 * L / 2 * W / 2.4).toFixed(1)} kWh`;
  $('m_geo').textContent = `pabellón ${L} × ${String(W).replace('.', ',')} m`;
}
let tMetricas = 0;
function aplicarCfg() { info(); construir(true); clearTimeout(tMetricas); tMetricas = setTimeout(cargarDia, 250); }
$('c_lugar').onchange = e => { cfg.lugar = e.target.value; construir(false); };
$('c_menos').onclick = () => { cfg.largo = LARGOS[Math.max(0, LARGOS.indexOf(cfg.largo) - 1)]; aplicarCfg(); };
$('c_mas').onclick = () => { cfg.largo = LARGOS[Math.min(LARGOS.length - 1, LARGOS.indexOf(cfg.largo) + 1)]; aplicarCfg(); };
document.querySelectorAll('#c_ancho button').forEach(b => b.onclick = () => { cfg.ancho = Number(b.dataset.a); aplicarCfg(); });
$('c_aplicar').onclick = async () => {
  try {
    const r = await fetch('/api/evento', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tipo: 'modulos', fuente: 'panel', valor: { tipo: 'pabellon', kit: 'parada_bus', largo: cfg.largo, ancho: cfg.ancho,
        n: Math.max(1, cfg.largo / 2 - 1), area_m2: cfg.largo * cfg.ancho } }) });
    $('c_aplicar').textContent = r.ok ? 'Aplicado ✓ (el simulador usa ya esta geometría)' : 'Error al aplicar';
  } catch { $('c_aplicar').textContent = 'Sin conexión'; }
  setTimeout(() => $('c_aplicar').textContent = 'Aplicar al refugio real', 2500);
};

// ---------------- métricas del día (abajo) ----------------
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const GRAF = {
  g_temp: { series: [['temp_calle', 'Calle', '--s2'], ['temp_cupula', 'Cerrado sin control', '--s5'], ['temp_oasi', 'Dentro (OASI)', '--s1'], ['t_aparente_oasi', 'Sensación dentro', '--s4']], u: '°', d: 1 },
  g_aire: { series: [['caudal_m3h', 'Caudal', '--s3']], u: ' m³/h', d: 0, cero: true },
  g_ener: { series: [['solar', 'Placas', '--s3'], ['consumo', 'Consumo', '--s2']], u: ' W', d: 0, cero: true },
  g_bat: { series: [['bateria', 'Batería', '--s1']], u: ' %', d: 0, min: 0, max: 100 },
};
let DIA = null;
async function cargarDia() {
  try {
    const r = await fetch(`/api/metricas/dia?largo=${cfg.largo}&ancho=${cfg.ancho}`);
    if (!r.ok) throw new Error(r.status);
    DIA = await r.json();
  } catch { DIA = null; }
  pintarDia();
}
function tiles() {
  const el = $('m_tiles');
  if (!DIA) { el.innerHTML = '<div class="tile"><small>Métricas</small><b>sin datos</b></div>'; return; }
  const s = DIA.series, r = DIA.resumen;
  const atMin = Math.min(...s.t_aparente_oasi), qMax = Math.max(...s.caudal_m3h);
  const T = [['°C menos que la calle (pico)', r.grados_reducidos_pico.toFixed(1) + ' °C'],
    ['Horas de calor peligroso evitadas', r.horas_riesgo_evitadas.toFixed(1) + ' h'],
    ['Energía solar del día', r.kwh_solares.toFixed(1) + ' kWh'], ['Autoconsumo', Math.round(r.pct_autoconsumo) + ' %'],
    ['Caudal máximo', Math.round(qMax).toLocaleString('es-ES') + ' m³/h'], ['Sensación mínima dentro', atMin.toFixed(1) + ' °C']];
  el.innerHTML = T.map(([k, v]) => `<div class="tile"><small>${k}</small><b>${v}</b></div>`).join('');
}
function pintarDia() { tiles(); for (const id of Object.keys(GRAF)) grafica(id); }
function grafica(id) {
  const g = GRAF[id], card = $(id);
  card.querySelector('.leyenda')?.remove(); card.querySelector('svg')?.remove(); card.querySelector('.tip')?.remove();
  if (!DIA) return;
  const S = DIA.series, hs = S.t.map(t => t / 3600);
  const series = g.series.filter(([k]) => Array.isArray(S[k])).map(([k, nom, c]) => ({ k, nom, col: css(c), v: S[k] }));
  if (series.length > 1) card.insertAdjacentHTML('beforeend', '<div class="leyenda">' + series.map(s => `<span><i style="background:${s.col}"></i>${s.nom}</span>`).join('') + '</div>');
  card.insertAdjacentHTML('beforeend', '<svg role="img"></svg><div class="tip"></div>');
  const svg = card.querySelector('svg'), W = svg.clientWidth || 320, H = 150, m = { l: 42, r: 8, t: 8, b: 20 };
  const vs = series.flatMap(s => s.v);
  let y0 = g.min ?? Math.min(...vs), y1 = g.max ?? Math.max(...vs);
  if (g.cero) y0 = Math.min(0, y0);
  if (y1 - y0 < 1e-6) y1 = y0 + 1;
  const pad = (y1 - y0) * 0.08; if (g.min === undefined && !g.cero) y0 -= pad; if (g.max === undefined) y1 += pad;
  const X = h => m.l + h / 24 * (W - m.l - m.r), Y = v => H - m.b - (v - y0) / (y1 - y0) * (H - m.t - m.b);
  let h = '';
  for (let i = 0; i <= 3; i++) { const v = y0 + (y1 - y0) * i / 3;
    h += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="${css('--grid')}"/><text x="${m.l - 5}" y="${Y(v) + 4}" text-anchor="end">${Math.round(v).toLocaleString('es-ES')}</text>`; }
  for (const hh of [0, 6, 12, 18, 24]) h += `<text x="${X(hh)}" y="${H - 5}" text-anchor="${hh === 0 ? 'start' : hh === 24 ? 'end' : 'middle'}">${hh}h</text>`;
  for (const s of series) {
    const d = s.v.map((v, i) => `${i ? 'L' : 'M'}${X(hs[i]).toFixed(1)},${Y(v).toFixed(1)}`).join('');
    h += `<path d="${d}" fill="none" stroke="${s.col}" stroke-width="2" stroke-linejoin="round"/>`;
  }
  h += `<line class="ahora" y1="${m.t}" y2="${H - m.b}" stroke="${css('--txt')}" stroke-width="1.5" stroke-dasharray="3 3"/>`;
  h += `<g class="pts"></g>`;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('aria-label', card.querySelector('h3').textContent); svg.innerHTML = h;
  g.dib = { svg, X, Y, hs, series, W };   // lo dibujado (g.series son las definiciones)
  const tip = card.querySelector('.tip');
  const horaDe = e => { const r = svg.getBoundingClientRect(); return Math.max(0, Math.min(24, ((e.clientX - r.left) * W / r.width - m.l) / (W - m.l - m.r) * 24)); };
  svg.onpointermove = e => {
    const hh = horaDe(e), i = Math.min(hs.length - 1, Math.max(0, Math.round(hh * 6) - 1));
    tip.innerHTML = `<div>${hhmm(hs[i])}</div>` + series.map(s => `<div><i style="background:${s.col}"></i>${s.nom}: <b>${s.v[i].toFixed(g.d)}${g.u}</b></div>`).join('');
    tip.style.display = 'block'; const r = svg.getBoundingClientRect();
    tip.style.left = Math.min((e.clientX - r.left) + 14, r.width - tip.offsetWidth) + 'px'; tip.style.top = '40px';
  };
  svg.onpointerleave = () => tip.style.display = 'none';
  svg.onclick = e => { hora = Math.max(5.5, Math.min(21.5, horaDe(e))); $('s_rango').value = hora; animando = false; $('s_play').textContent = '▶'; aplicarSol(); };
  marcarHora();
}
function marcarHora() {   // línea vertical y puntos con el valor a la hora del sol de arriba
  for (const { dib: g, d, u } of Object.values(GRAF)) {
    if (!g?.svg?.isConnected) continue;
    const x = g.X(hora); const l = g.svg.querySelector('.ahora'); l.setAttribute('x1', x); l.setAttribute('x2', x);
    const i = Math.min(g.hs.length - 1, Math.max(0, Math.round(hora * 6) - 1));
    g.svg.querySelector('.pts').innerHTML = g.series.map(s => `<circle cx="${g.X(g.hs[i])}" cy="${g.Y(s.v[i])}" r="4" fill="${s.col}" stroke="${css('--card2')}" stroke-width="2"/>` +
      `<text class="lab" x="${Math.min(g.X(g.hs[i]) + 7, g.W - 60)}" y="${g.Y(s.v[i]) - 6}">${s.v[i].toFixed(d)}${u}</text>`).join('');
  }
}

// ---------------- barra arrastrable: reparte alto entre simulación y métricas ----------------
const raiz = document.documentElement;
try { const g = localStorage.getItem('oasi_alto_metricas'); if (g) raiz.style.setProperty('--alto-metricas', g); } catch {}
(function () {
  const barra = $('barra'); let arr = false;
  const fijar = px => { const v = Math.max(120, Math.min(innerHeight - 180, px)) + 'px'; raiz.style.setProperty('--alto-metricas', v);
    try { localStorage.setItem('oasi_alto_metricas', v); } catch {} };
  barra.addEventListener('pointerdown', e => { arr = true; barra.setPointerCapture(e.pointerId); });
  barra.addEventListener('pointermove', e => { if (arr) fijar(innerHeight - e.clientY - 5); });
  barra.addEventListener('pointerup', () => { arr = false; pintarDia(); });
  barra.addEventListener('dblclick', () => { fijar($('abajo').offsetHeight > innerHeight * 0.5 ? innerHeight * 0.36 : innerHeight * 0.7); pintarDia(); });
  barra.addEventListener('keydown', e => { const h = $('abajo').offsetHeight;
    if (e.key === 'ArrowUp') fijar(h + 30); if (e.key === 'ArrowDown') fijar(h - 30); });
})();
function ajustar() {
  const w = arriba.clientWidth, h = arriba.clientHeight;
  if (!w || !h) return;
  renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
}
new ResizeObserver(ajustar).observe(arriba);
let tRe = 0; new ResizeObserver(() => { clearTimeout(tRe); tRe = setTimeout(pintarDia, 150); }).observe($('abajo'));

// ---------------- arranque ----------------
$('c_lugar').value = cfg.lugar;
info(); construir(true); conectar(); hud(); cargarDia(); ajustar();
const reloj = new THREE.Clock();
renderer.setAnimationLoop(() => {
  const dt = Math.min(reloj.getDelta(), 0.1);
  if (animando) { hora += dt * 0.5; if (hora > 21.5) hora = 5.5; $('s_rango').value = hora; aplicarSol(); }
  refugio.actualizar(dt); controls.update(); renderer.render(scene, camera);
});
