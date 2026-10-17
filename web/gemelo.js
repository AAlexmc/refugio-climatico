// Gemelo 3D vivo: consume el WebSocket de eventos (docs/contratos.md) y mueve el refugio.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { construirRefugio } from './oasi3d.js';
import { construirEntorno, LUGAR_POR_KIT } from './entorno.js';

const REFUGIO = new URLSearchParams(location.search).get('refugio') || 'R1';
const $ = id => document.getElementById(id);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.prepend(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x9ec9e6);
scene.fog = new THREE.Fog(0x9ec9e6, 25, 70);
const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 200);
const controls = new OrbitControls(camera, renderer.domElement);
controls.maxPolarAngle = Math.PI * 0.49; controls.enableDamping = true;

const hemi = new THREE.HemisphereLight(0xffffff, 0x556655, 0.9); scene.add(hemi);
scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
const sol = new THREE.DirectionalLight(0xfff2d8, 2); sol.position.set(8, 14, 6); scene.add(sol);
sol.castShadow = true; sol.shadow.mapSize.set(2048, 2048); sol.shadow.bias = -0.0005;
Object.assign(sol.shadow.camera, { left: -14, right: 14, top: 14, bottom: -14, near: 1, far: 50 });
scene.add(sol.target);
let entorno = null;   // bus / plaza / terraza (web/entorno.js)

// estado acumulado: se reaplica si el refugio se reconstruye (evento `modulos`)
const E = { claraboya: 0, ac: false, nebulizador: false, ventilador: false, temp: null, solar: 0, bateria: 0, noche: false };
let temp_ext = null, aforo = null, personas = [], desmayo = { activo: false, persona: null };
let cfg = { kit: 'parada_bus', n: 2, tipo: 'cupula', cubierta: 'vidrio_control_solar', arbol: true, lugar: new URLSearchParams(location.search).get('lugar') || 'bus' }, refugio = null;

function construir() {
  refugio?.dispose();
  if (!entorno || entorno.lugar !== cfg.lugar) { entorno?.dispose(); entorno = construirEntorno(scene, cfg.lugar); entorno.lugar = cfg.lugar; }
  refugio = construirRefugio(scene, cfg);
  refugio.set(E); refugio.setPersonas(personas); refugio.setDesmayo(desmayo);
  controls.target.copy(refugio.centro);
  const d = Math.max(8, cfg.n * 2.2 + 4);
  camera.position.set(d * 0.9, d * 0.6, d * 0.5 + 2);
}
construir();

function dia(radiacion) {
  const noche = radiacion <= 0;
  E.noche = noche; refugio.set({ noche });
  const f = noche ? 0 : Math.min(radiacion / 1000, 1);
  sol.intensity = f * 3; hemi.intensity = noche ? 0.12 : 0.35 + 0.65 * f;
  scene.background.set(noche ? 0x070b16 : 0x9ec9e6); scene.fog.color.copy(scene.background);
}
dia(800);

function hud() {
  const f = (v, u, d = 1) => v == null ? '—' : `${(+v).toFixed(d)} ${u}`;
  $('h_ref').textContent = REFUGIO;
  $('h_temp').textContent = f(E.temp, '°C'); $('h_ext').textContent = f(temp_ext, '°C');
  $('h_aforo').textContent = aforo ?? '—'; $('h_bat').textContent = f(E.bateria, '%', 0);
  $('h_sol').textContent = f(E.solar, 'W', 0); $('h_cla').textContent = Math.round(E.claraboya * 100) + ' %';
  $('h_ac').textContent = E.ac ? 'ON' : 'off'; $('h_neb').textContent = E.nebulizador ? 'ON' : 'off';
  $('h_ven').textContent = E.ventilador ? 'ON' : 'off';
}

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
      E[ev.tipo] = BOOL.has(ev.tipo) ? !!v : Number(v);
      refugio.set({ [ev.tipo]: E[ev.tipo] }); break;
    case 'temp_ext': temp_ext = Number(v); break;
    case 'aforo': aforo = v; break;
    case 'radiacion': dia(Number(v)); break;
    case 'personas': personas = Array.isArray(v) ? v : []; refugio.setPersonas(personas); break;
    case 'desmayo': desmayo = { activo: !!v?.activo, persona: v?.persona ?? null }; refugio.setDesmayo(desmayo); break;
    case 'alerta':
      if (v?.codigo === 'afluencia') {
        const on = v.nivel !== 'info';
        $('afluencia').style.display = on ? 'block' : 'none';
        if (on) $('afluencia').textContent = '👥 ' + v.mensaje;
      }
      if (v?.codigo === 'desmayo') {
        const on = v.nivel === 'critico';
        $('banner').style.display = on ? 'block' : 'none';
        if (on) $('banner').textContent = 'Alerta 061 · ' + (v.mensaje || 'desmayo');
      } break;
    case 'modulos':
      if (v && v.kit && v.n && (v.kit !== cfg.kit || v.n !== cfg.n || (v.tipo || 'cupula') !== cfg.tipo)) { cfg = { ...cfg, ...v, tipo: v.tipo || 'cupula' }; construir(); pintarCfg(); } break;
  }
  hud();
}

function conectar() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  const est = $('estado');
  ws.onopen = () => { est.textContent = 'en vivo'; est.className = ''; };
  ws.onclose = () => { est.textContent = 'sin conexión'; est.className = 'off'; setTimeout(conectar, 1000); };
  ws.onerror = () => ws.close();
  ws.onmessage = m => { try { evento(JSON.parse(m.data)); } catch (e) { console.warn('evento ignorado', e); } };
}
conectar(); hud();

// --- configuración dentro del gemelo (mismo modelo que /configurador.html) ---
const AFORO_MOD = 10, KWP_MOD = 0.8, KWH_MOD = 2.5;
function pintarCfg() {
  $('c_tipo').value = cfg.tipo; $('c_lugar').value = cfg.lugar; $('c_kit').value = cfg.kit; $('c_cub').value = cfg.cubierta; $('c_arbol').checked = cfg.arbol;
  $('c_n').textContent = cfg.n;
  const cup = cfg.tipo === 'cupula';
  for (const id of ['l_kit', 'l_n', 'l_cub', 'l_arb']) $(id).style.display = cup ? '' : 'none';
  const n = cup ? cfg.n : 1;
  $('c_info').textContent = `Aforo ${n * AFORO_MOD} · FV ${(n * KWP_MOD + (cup && cfg.arbol || cfg.tipo === 'arbol_solar' ? 1.5 : 0)).toFixed(1)} kWp · batería ${(n * KWH_MOD).toFixed(1)} kWh`;
}
function cambiar(p) { cfg = { ...cfg, ...p }; cfg.n = Math.max(1, Math.min(8, cfg.n)); construir(); pintarCfg(); }
$('c_tipo').onchange = e => cambiar({ tipo: e.target.value });
$('c_kit').onchange = e => cambiar({ kit: e.target.value, lugar: LUGAR_POR_KIT[e.target.value] || cfg.lugar });
$('c_lugar').onchange = e => cambiar({ lugar: e.target.value });
$('c_cub').onchange = e => cambiar({ cubierta: e.target.value });
$('c_arbol').onchange = e => cambiar({ arbol: e.target.checked });
$('c_menos').onclick = () => cambiar({ n: cfg.n - 1 });
$('c_mas').onclick = () => cambiar({ n: cfg.n + 1 });
$('c_aplicar').onclick = async () => {
  const n = cfg.tipo === 'cupula' ? cfg.n : 1;
  try {
    const r = await fetch('/api/evento', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tipo: 'modulos', fuente: 'panel', valor: { kit: cfg.kit, n, area_m2: n * 16, tipo: cfg.tipo } }) });
    $('c_aplicar').textContent = r.ok ? 'Aplicado ✓' : 'Error al aplicar';
  } catch { $('c_aplicar').textContent = 'Sin conexión'; }
  setTimeout(() => $('c_aplicar').textContent = 'Aplicar al refugio real', 2000);
};
pintarCfg();

function ajustar() {
  renderer.setSize(innerWidth, innerHeight);
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
}
addEventListener('resize', ajustar); ajustar();

const reloj = new THREE.Clock();
renderer.setAnimationLoop(() => {
  const dt = Math.min(reloj.getDelta(), 0.1);
  refugio.actualizar(dt); controls.update(); renderer.render(scene, camera);
});
