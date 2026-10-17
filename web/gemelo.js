// Gemelo 3D vivo: consume el WebSocket de eventos (docs/contratos.md) y mueve el refugio.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { construirRefugio } from './oasi3d.js';

const REFUGIO = new URLSearchParams(location.search).get('refugio') || 'R1';
const $ = id => document.getElementById(id);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
document.body.prepend(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x9ec9e6);
scene.fog = new THREE.Fog(0x9ec9e6, 25, 70);
const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 200);
const controls = new OrbitControls(camera, renderer.domElement);
controls.maxPolarAngle = Math.PI * 0.49; controls.enableDamping = true;

const hemi = new THREE.HemisphereLight(0xffffff, 0x556655, 0.9); scene.add(hemi);
const sol = new THREE.DirectionalLight(0xfff2d8, 2); sol.position.set(6, 12, 5); scene.add(sol);
const suelo = new THREE.Mesh(new THREE.CircleGeometry(60, 48), new THREE.MeshStandardMaterial({ color: 0x6c7a6c, roughness: 1 }));
suelo.rotation.x = -Math.PI / 2; suelo.position.y = -0.11; scene.add(suelo);

// estado acumulado: se reaplica si el refugio se reconstruye (evento `modulos`)
const E = { claraboya: 0, ac: false, nebulizador: false, ventilador: false, temp: null, solar: 0, bateria: 0, noche: false };
let temp_ext = null, aforo = null, personas = [], desmayo = { activo: false, persona: null };
let cfg = { kit: 'parada_bus', n: 2 }, refugio = null;

function construir() {
  refugio?.dispose();
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
      if (v && v.kit && v.n && (v.kit !== cfg.kit || v.n !== cfg.n)) { cfg = { kit: v.kit, n: v.n }; construir(); } break;
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
