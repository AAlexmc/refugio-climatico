// Configurador modular: elige kit y nº de módulos, ve el 3D y las cifras, y lo aplica al refugio.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { construirRefugio } from './oasi3d.js';

// Provisional hasta datos/kits.json (O3·B). Cifras POR MÓDULO.
const KITS = {
  parada_bus:          { nombre: 'Parada de bus',       n: 2, area_m2: 9, aforo: 10, fv_m2: 4, bateria_kwh: 2.5, coste_eur: 6500 },
  terraza_comunitaria: { nombre: 'Terraza comunitaria', n: 4, area_m2: 9, aforo: 10, fv_m2: 4, bateria_kwh: 2.5, coste_eur: 6500 },
  terraza_privada:     { nombre: 'Terraza privada',     n: 1, area_m2: 9, aforo: 10, fv_m2: 4, bateria_kwh: 2.5, coste_eur: 6500 },
};
let origen = 'constantes provisionales';

// Acepta {kits:{id:{...}}} o {id:{...}}. Campos por módulo o totales (se dividen entre modulos_defecto).
async function cargarKits() {
  for (const url of ['/kits.json', '/api/kits']) {
    try {
      const r = await fetch(url); if (!r.ok) continue;
      const j = await r.json(), src = j.kits || j;
      let ok = false;
      for (const id of Object.keys(KITS)) {
        const k = src[id]; if (!k || typeof k !== 'object') continue;
        const nd = Number(k.modulos_defecto ?? k.modulos ?? k.n) || KITS[id].n;
        const div = k.por_modulo ? 1 : nd;
        const num = (...ks) => { for (const c of ks) if (typeof k[c] === 'number') return k[c] / div; };
        KITS[id] = { ...KITS[id], n: nd,
          area_m2: num('area_m2', 'm2') ?? KITS[id].area_m2, aforo: num('aforo_max', 'aforo') ?? KITS[id].aforo,
          fv_m2: num('fv_m2', 'm2_fv') ?? KITS[id].fv_m2, bateria_kwh: num('bateria_kwh', 'kwh_bateria') ?? KITS[id].bateria_kwh,
          coste_eur: num('coste_materiales_eur', 'coste_eur', 'coste') ?? KITS[id].coste_eur };
        ok = true;
      }
      if (ok) { origen = 'datos ' + url; return; }
    } catch (e) { /* sin endpoint: se quedan las constantes */ }
  }
}

const $ = id => document.getElementById(id);
let kit = 'parada_bus', n = KITS[kit].n, refugio = null;

const cont = $('vista');
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
cont.appendChild(renderer.domElement);
const scene = new THREE.Scene(); scene.background = new THREE.Color(0x9ec9e6);
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 200);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.maxPolarAngle = Math.PI * 0.49;
scene.add(new THREE.HemisphereLight(0xffffff, 0x556655, 1));
const sol = new THREE.DirectionalLight(0xfff2d8, 2.2); sol.position.set(6, 12, 5); scene.add(sol);
const suelo = new THREE.Mesh(new THREE.CircleGeometry(50, 40), new THREE.MeshStandardMaterial({ color: 0x6c7a6c, roughness: 1 }));
suelo.rotation.x = -Math.PI / 2; suelo.position.y = -0.11; scene.add(suelo);

function reconstruir() {
  refugio?.dispose();
  refugio = construirRefugio(scene, { kit, n });
  refugio.set({ claraboya: 0.5, solar: 600 * n, bateria: 75, temp: 25, ac: true });
  controls.target.copy(refugio.centro);
  const d = Math.max(9, n * 1.8 + 6);
  camera.position.set(d * 0.9, d * 0.55, d * 0.4 + 3);
}

function pintar() {
  const K = KITS[kit];
  $('n').textContent = n;
  document.querySelectorAll('#kits button').forEach(b => b.classList.toggle('sel', b.dataset.kit === kit));
  const f = (v, d = 0) => v.toLocaleString('es-ES', { maximumFractionDigits: d });
  $('cifras').innerHTML = [
    ['Área', `${f(K.area_m2 * n)} m²`], ['Aforo máximo', `${f(K.aforo * n)} personas`],
    ['Placas FV', `${f(K.fv_m2 * n)} m²`], ['Batería', `${f(K.bateria_kwh * n, 1)} kWh`],
    ['Coste materiales (est.)', `${f(K.coste_eur * n)} €`],
  ].map(([a, b]) => `<tr><td>${a}</td><td>${b}</td></tr>`).join('');
  $('origen').textContent = 'Cifras: ' + origen;
  reconstruir();
}

function iniciar() {
  const kc = $('kits');
  for (const [id, k] of Object.entries(KITS)) {
    const b = document.createElement('button'); b.textContent = k.nombre; b.dataset.kit = id;
    b.onclick = () => { kit = id; n = KITS[id].n; pintar(); }; kc.appendChild(b);
  }
  $('mas').onclick = () => { if (n < 8) { n++; pintar(); } };
  $('menos').onclick = () => { if (n > 1) { n--; pintar(); } };
  $('aplicar').onclick = async () => {
    const m = $('msg'); m.textContent = 'enviando…';
    try {
      const r = await fetch('/api/evento', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tipo: 'modulos', valor: { kit, n, area_m2: KITS[kit].area_m2 * n }, fuente: 'panel' }) });
      m.textContent = r.ok ? 'Aplicado al refugio.' : 'Error del servidor: ' + r.status;
    } catch (e) { m.textContent = 'Sin conexión con el servidor.'; }
  };
  pintar();
}

function ajustar() {
  const w = cont.clientWidth || 300, h = cont.clientHeight || 300;
  renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix();
}
addEventListener('resize', ajustar); new ResizeObserver(ajustar).observe(cont);

const reloj = new THREE.Clock();
renderer.setAnimationLoop(() => {
  refugio?.actualizar(Math.min(reloj.getDelta(), 0.1)); controls.update(); renderer.render(scene, camera);
});

iniciar(); ajustar();
cargarKits().then(() => { n = KITS[kit].n; pintar(); });
