// Geometría procedural del refugio OASI (compartida por gemelo.js y configurador.js).
// Sin modelos externos. Unidades: metros. Marco three: x lateral, y arriba, z hacia el fondo NEGATIVO.
//
// Planta: módulos de 3 m x 3 m acoplados en línea a lo largo de z (bóveda de cañón con
// extremos redondeados -> acopla en línea sin juntas). Frente (cámara) en z = 0; el módulo i
// ocupa z in [-3(i+1), -3i]. terraza_comunitaria = rejilla 2 columnas x ceil(n/2) filas.
//
// Marco de personas (docs/contratos.md): x lateral, y fondo desde la cámara.
//   three = (x, 0, -y)  y SIN offset: el frente del refugio es la cámara, así y = 1..6 m cae
//   dentro de un refugio de n >= 2 módulos (6 m de fondo). x = 0 es el eje del refugio (centrado).
//   Las posiciones se recortan al interior de la planta para que ningún avatar quede fuera.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone as clonarRig } from 'three/addons/utils/SkeletonUtils.js';

export const LADO = 4;          // m, lado del módulo
const BASE = 2.2;               // altura de los pilares / arranque de la bóveda (persona 1,7 m)
const R = LADO / 2;             // radio de la bóveda
const TOPE = BASE + R;          // altura de la corona

const _tex = {};
function circulo() {
  if (_tex.c) return _tex.c;
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d');
  const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
  return (_tex.c = new THREE.CanvasTexture(c));
}
function texFV(repX, repY) {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d');
  g.fillStyle = '#0b1f4a'; g.fillRect(0, 0, 128, 128);
  g.strokeStyle = '#5f86c9'; g.lineWidth = 2;
  for (let i = 0; i <= 128; i += 32) { g.beginPath(); g.moveTo(i, 0); g.lineTo(i, 128); g.stroke();
    g.beginPath(); g.moveTo(0, i); g.lineTo(128, i); g.stroke(); }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(repX, repY);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

export function crearEtiqueta(texto, color = '#ffffff') {
  const c = document.createElement('canvas'); c.width = 256; c.height = 64;
  const g = c.getContext('2d');
  g.fillStyle = 'rgba(10,20,15,0.75)'; g.fillRect(0, 8, 256, 48);
  g.font = 'bold 30px system-ui, sans-serif'; g.fillStyle = color;
  g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(texto, 128, 33);
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), depthTest: false, transparent: true }));
  s.scale.set(0.9, 0.225, 1); s.renderOrder = 10;
  return s;
}

function colorTemp(t) {
  if (t == null || Number.isNaN(t)) return 0x9fd8c0;
  if (t < 24) return 0x4aa8ff;
  if (t <= 27) return 0x4cd98a;
  if (t <= 32) return 0xff9a3c;
  return 0xff4040;
}

// Partículas con vida; `emitir(i, pos, vel)` rellena una nueva partícula.
function crearChorro(n, { color, size, opacity, emitir, vida, grav = 0 }) {
  const pos = new Float32Array(n * 3).fill(-100), vel = new Float32Array(n * 3), life = new Float32Array(n);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const mat = new THREE.PointsMaterial({ color, size, map: circulo(), transparent: true, opacity,
    depthWrite: false, sizeAttenuation: true });
  const pts = new THREE.Points(geo, mat); pts.frustumCulled = false;
  return {
    pts,
    update(dt, activo) {
      for (let i = 0; i < n; i++) {
        if (life[i] <= 0) {
          if (activo && Math.random() < dt * n / vida) {
            life[i] = vida * (0.6 + Math.random() * 0.4);
            emitir(pos, vel, i * 3);
          } else continue;
        }
        life[i] -= dt;
        if (life[i] <= 0) { pos[i * 3 + 1] = -100; continue; }
        vel[i * 3 + 1] -= grav * dt;
        pos[i * 3] += vel[i * 3] * dt; pos[i * 3 + 1] += vel[i * 3 + 1] * dt; pos[i * 3 + 2] += vel[i * 3 + 2] * dt;
        if (pos[i * 3 + 1] < (grav ? 0.75 : 0.1) && (grav ? vel[i * 3 + 1] < 0 : true)) life[i] = 0;
      }
      geo.attributes.position.needsUpdate = true;
    },
  };
}

// Modelos FurniMesh opcionales (web/modelos/CREDITOS.md). Si falla la carga o ?sin_modelos=1,
// queda la geometría procedural, sin error.
const MODELOS = {
  banco: 'modelos/furnimesh/banco_enredaderas.glb',
  jardin: 'modelos/furnimesh/jardin_vertical.glb',
  parada: 'modelos/furnimesh/parada.glb',
  persona: 'modelos/persona.glb',   // «An Elderly Man» (BELAZ, CC-BY 4.0), rig Mixamo; ver modelos/CREDITOS.md
};
const _glb = {};
function cargarGLB(clave) {
  if (new URLSearchParams(globalThis.location?.search || '').has('sin_modelos')) return Promise.resolve(null);
  return (_glb[clave] ??= new Promise(res => {
    new GLTFLoader().load(MODELOS[clave], gltf => res(gltf.scene), undefined, () => res(null));
  }).catch(() => null));
}
// Clona el modelo, lo orienta (eje largo horizontal -> z, o sin girar), lo escala con Box3 y lo apoya en y = 0.
// medida: {largo} = dimensión horizontal mayor en m; {alto} = altura en m.
function colocarModelo(base, { largo, alto, giroY = 0 }) {
  const m = base.clone(true);
  const caja = new THREE.Box3().setFromObject(m), sz = caja.getSize(new THREE.Vector3());
  const k = alto ? alto / sz.y : largo / Math.max(sz.x, sz.z);
  const pivote = new THREE.Group();
  m.scale.multiplyScalar(k);
  const c2 = new THREE.Box3().setFromObject(m), ctr = c2.getCenter(new THREE.Vector3());
  m.position.set(-ctr.x, -c2.min.y, -ctr.z);
  const largoEnX = sz.x > sz.z;
  pivote.add(m);
  pivote.rotation.y = giroY + (largo && largoEnX ? Math.PI / 2 : 0);
  return pivote;
}

function texTarima() {
  if (_tex.t) return _tex.t;
  const c = document.createElement('canvas'); c.width = c.height = 256;
  const g = c.getContext('2d');
  for (let i = 0; i < 16; i++) { g.fillStyle = i % 2 ? '#a7835b' : '#b48e63'; g.fillRect(0, i * 16, 256, 16);
    g.fillStyle = 'rgba(0,0,0,.25)'; g.fillRect(0, i * 16 + 15, 256, 1); }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(2, 2);
  t.colorSpace = THREE.SRGBColorSpace; return (_tex.t = t);
}

const ROPA = [0x2f6db5, 0xc0443a, 0x3a8f5a, 0xe0a030, 0x6b4fa8, 0x333a44, 0xd06c9a, 0x1f8a8a];
const PIEL = [0xf0c8a0, 0xd9a77a, 0xa8704a, 0x7a4a2c, 0xf5d5b8];
const PELO = [0x2a1d14, 0x4a3020, 0x8a6a3a, 0x111111, 0xb0a090];

// --- persona con rig: pose estática por estado (de_pie / sentado / suelo) ---
const _v1 = new THREE.Vector3(), _v2 = new THREE.Vector3(), _d = new THREE.Vector3();
const _qa = new THREE.Quaternion(), _qb = new THREE.Quaternion(), _qc = new THREE.Quaternion(), _qr = new THREE.Quaternion();
function alinearHueso(hueso, hijo, dirLocal, raiz) {
  if (!hueso || !hijo) return;
  raiz.getWorldQuaternion(_qr);
  _d.copy(dirLocal).applyQuaternion(_qr).normalize();
  hueso.updateMatrixWorld(true);
  hueso.getWorldPosition(_v1); hijo.getWorldPosition(_v2); _v2.sub(_v1);
  if (_v2.lengthSq() < 1e-10) return;
  _qa.setFromUnitVectors(_v2.normalize(), _d);
  hueso.getWorldQuaternion(_qb).premultiply(_qa);
  hueso.parent.getWorldQuaternion(_qc).invert();
  hueso.quaternion.copy(_qc.multiply(_qb));
}
const ABAJO = new THREE.Vector3(0, -1, 0), DELANTE = new THREE.Vector3(0, -0.05, 1);
function posar(rig, estado) {
  const h = rig.huesos;
  for (const [b, q] of rig.bind) b.quaternion.copy(q);
  const raiz = rig.raiz;
  raiz.updateMatrixWorld(true);
  for (const lado of ['Left', 'Right']) {
    const sx = lado === 'Left' ? 1 : -1;
    alinearHueso(h[lado + 'Arm'], h[lado + 'ForeArm'], new THREE.Vector3(0.12 * sx, -1, 0.02), raiz);
    alinearHueso(h[lado + 'ForeArm'], h[lado + 'Hand'], estado === 'sentado' ? new THREE.Vector3(0.05 * sx, -0.4, 1) : new THREE.Vector3(0.05 * sx, -1, 0.12), raiz);
    if (estado === 'sentado') {
      alinearHueso(h[lado + 'UpLeg'], h[lado + 'Leg'], DELANTE, raiz);
      alinearHueso(h[lado + 'Leg'], h[lado + 'Foot'], ABAJO, raiz);
    } else {
      alinearHueso(h[lado + 'UpLeg'], h[lado + 'Leg'], new THREE.Vector3(0.03 * sx, -1, 0), raiz);
      alinearHueso(h[lado + 'Leg'], h[lado + 'Foot'], ABAJO, raiz);
    }
  }
}
function nuevoRig(base, escala) {
  const raiz = new THREE.Group();
  const m = clonarRig(base); m.scale.setScalar(escala); raiz.add(m);
  const huesos = {}, bind = new Map(), mats = [];
  m.traverse(o => {
    if (o.isBone) { huesos[o.name.replace(/_\d+$/, '')] ??= o; bind.set(o, o.quaternion.clone()); }
    if (o.isMesh) { o.castShadow = true; o.frustumCulled = false; o.material = o.material.clone(); mats.push(o.material); }
  });
  return { raiz, huesos, bind, mats };
}

function aleatorio(semilla) { let s = semilla; return () => (s = (s * 16807) % 2147483647) / 2147483647; }

const CUPULAS = {   // material de la cubierta (datos/kits.json § materiales_cubierta)
  vidrio_control_solar: { color: 0xcfeee0, transmission: 0.9, roughness: 0.05, att: 0x9fe0c0 },
  etfe_3_capas_frit: { color: 0xeaf4ff, transmission: 0.7, roughness: 0.25, att: 0xd0e4ff },
  policarbonato_opal_ir: { color: 0xf4f1e6, transmission: 0.45, roughness: 0.55, att: 0xffffff },
};
export function construirRefugio(scene, { kit = 'parada_bus', n = 2, arbol: conArbol = true,
                                          cubierta = 'vidrio_control_solar', etiquetas = true, tipo = 'cupula' } = {}) {
  // tipo: 'cupula' (módulos con bóveda) | 'arbol_solar' | 'jardin' (jardín vertical + pérgola FV) | 'banco_solar'
  const esCupula = tipo === 'cupula';
  if (!esCupula) n = 1;
  const cup = CUPULAS[cubierta] || CUPULAS.vidrio_control_solar;
  n = Math.max(1, Math.min(8, Math.round(n)));
  const g = new THREE.Group(); g.name = 'refugio';
  const cols = kit === 'terraza_comunitaria' ? 2 : 1;
  const filas = Math.ceil(n / cols);
  const modulos = [];   // {cx, cz, col}
  for (let i = 0; i < n; i++) {
    const col = i % cols, fila = Math.floor(i / cols);
    modulos.push({ cx: (col - (cols - 1) / 2) * LADO, cz: -(fila + 0.5) * LADO, col });
  }
  const filasCol = Array.from({ length: cols }, (_, c) => modulos.filter(m => m.col === c).length);
  const limites = esCupula ? { minX: -cols * R, maxX: cols * R, minZ: -filas * LADO, maxZ: 0 }
                           : { minX: -3, maxX: 3, minZ: -6, maxZ: 0 };

  // --- materiales ---
  const mVidrio = new THREE.MeshPhysicalMaterial({ color: cup.color, transmission: cup.transmission, roughness: cup.roughness,
    thickness: 0.08, ior: 1.45, transparent: true, side: THREE.DoubleSide, attenuationColor: new THREE.Color(cup.att),
    attenuationDistance: 3 });
  const mEstruct = new THREE.MeshStandardMaterial({ color: 0x3c4a44, metalness: 0.7, roughness: 0.4 });
  const mSuelo = new THREE.MeshStandardMaterial({ map: texTarima(), roughness: 0.8 });
  const mBanco = new THREE.MeshStandardMaterial({ color: 0xb98a55, roughness: 0.7 });
  const mTierra = new THREE.MeshStandardMaterial({ color: 0x4a3322, roughness: 1 });
  const mMacetero = new THREE.MeshStandardMaterial({ color: 0x7a7a72, roughness: 0.8 });
  const mVerde = [0x2f9a4a, 0x3fb858, 0x23803c].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.8 }));
  const mAire = new THREE.MeshBasicMaterial({ color: 0x9fd8c0, transparent: true, opacity: 0.12, depthWrite: false });
  const mFV = [];   // un material por tira (textura con su repetición)
  const mClar = new THREE.MeshPhysicalMaterial({ color: 0xcfeee0, transmission: 0.85, roughness: 0.05, transparent: true,
    side: THREE.DoubleSide });

  // --- suelo ---
  for (let c = 0; c < (esCupula ? cols : 0); c++) {
    const L = filasCol[c] * LADO, cx = (c - (cols - 1) / 2) * LADO;
    const suelo = new THREE.Mesh(new THREE.BoxGeometry(LADO, 0.1, L), mSuelo);
    suelo.position.set(cx, -0.05, -L / 2); suelo.receiveShadow = true; g.add(suelo);

    // bóveda de cañón (eje z): theta=PI es la corona
    const bov = new THREE.CylinderGeometry(R, R, L, 32, 1, true, Math.PI / 2, Math.PI); bov.rotateX(Math.PI / 2);
    const mb = new THREE.Mesh(bov, mVidrio); mb.position.set(cx, BASE, -L / 2); g.add(mb);
    // aire interior (tinte por temperatura)
    const aire = new THREE.Mesh(new THREE.CylinderGeometry(R * 0.97, R * 0.97, L, 32, 1, false, Math.PI / 2, Math.PI), mAire);
    aire.geometry.rotateX(Math.PI / 2); aire.position.set(cx, BASE, -L / 2); g.add(aire);
    // extremos redondeados (cuartos de esfera)
    for (const [zEnd, phi] of [[0, 0], [-L, Math.PI]]) {
      const cap = new THREE.Mesh(new THREE.SphereGeometry(R, 24, 12, phi, Math.PI, 0, Math.PI / 2), mVidrio);
      cap.position.set(cx, BASE, zEnd); g.add(cap);
    }
    // placas FV fuera, en la corona (dos tiras a cada lado de la claraboya)
    for (const ini of [Math.PI + 0.45, Math.PI - 1.05]) {
      const geo = new THREE.CylinderGeometry(R + 0.04, R + 0.04, L - 0.2, 12, 1, true, ini, 0.6); geo.rotateX(Math.PI / 2);
      const mat = new THREE.MeshStandardMaterial({ map: texFV(2, filasCol[c] * 2), color: 0xffffff, roughness: 0.35,
        metalness: 0.4, side: THREE.DoubleSide, emissive: 0x3a7bff, emissiveIntensity: 0 });
      mFV.push(mat);
      const p = new THREE.Mesh(geo, mat); p.position.set(cx, BASE, -L / 2); g.add(p);
    }
    // pilares y larguero
    for (const sx of [-R, R]) for (let k = 0; k <= filasCol[c]; k++) {
      const pil = new THREE.Mesh(new THREE.BoxGeometry(0.06, BASE, 0.06), mEstruct);
      pil.position.set(cx + sx, BASE / 2, -k * LADO); g.add(pil);
    }
    for (const sx of [-R, R]) {
      const lar = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, L), mEstruct);
      lar.position.set(cx + sx, BASE, -L / 2); g.add(lar);
    }
  }

  // --- por módulo: claraboya, banco, jardinera, toberas ---
  const claraboyas = [];
  const toberasAC = [], toberasNeb = [], bancos = [];
  (esCupula ? modulos : []).forEach((m, i) => {
    const rnd = aleatorio(17 + i * 31);
    // claraboya: panel con bisagra en el borde -x; gira sobre z (eje de la línea)
    const piv = new THREE.Group(); piv.position.set(m.cx - 0.45, TOPE + 0.05, m.cz);
    const panel = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.04, 1.1), mClar); panel.position.x = 0.45;
    const marco = new THREE.Mesh(new THREE.BoxGeometry(0.94, 0.03, 1.14), mEstruct); marco.position.set(0.45, -0.03, 0);
    piv.add(panel, marco); g.add(piv); claraboyas.push(piv);
    // banco y jardinera (lados opuestos; alternan por módulo)
    const lado = i % 2 === 0 ? -1 : 1;
    const banco = new THREE.Group();
    const asiento = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.06, 2.0), mBanco); asiento.position.y = 0.45;
    const resp = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.4, 2.0), mBanco); resp.position.set(-0.2 * lado, 0.68, 0);
    const pata1 = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.45, 0.06), mEstruct); pata1.position.set(0, 0.22, 0.85);
    const pata2 = pata1.clone(); pata2.position.z = -0.85;
    banco.add(asiento, resp, pata1, pata2); banco.position.set(m.cx + lado * 1.1, 0, m.cz); g.add(banco);
    bancos.push({ banco, x: m.cx + lado * 1.1, z: m.cz, lado });
    const jard = new THREE.Group();
    const caja = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.4, 1.2), mMacetero); caja.position.y = 0.2;
    const tierra = new THREE.Mesh(new THREE.BoxGeometry(0.44, 0.04, 1.14), mTierra); tierra.position.y = 0.41;
    jard.add(caja, tierra);
    for (let k = 0; k < 5; k++) {
      const mv = mVerde[Math.floor(rnd() * 3)];
      const pl = k % 2 ? new THREE.Mesh(new THREE.ConeGeometry(0.11, 0.4 + rnd() * 0.2, 8), mv)
                       : new THREE.Mesh(new THREE.SphereGeometry(0.15 + rnd() * 0.06, 10, 8), mv);
      pl.position.set((rnd() - 0.5) * 0.25, 0.65 + rnd() * 0.1, -0.5 + k * 0.25); jard.add(pl);
    }
    jard.position.set(m.cx - lado * 1.15, 0, m.cz + 0.1); g.add(jard);
    toberasAC.push({ x: m.cx + lado * 1.15, z: m.cz, dir: -lado });
    toberasNeb.push({ x: m.cx, z: m.cz });
  });

  // --- unidad de AC exterior (lado +x, módulo del frente) y batería (lado -x) ---
  const m0 = modulos[0];
  const ac = new THREE.Group();
  const cuerpoAC = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.6, 0.8), new THREE.MeshStandardMaterial({ color: 0xdfe5e2, roughness: 0.5 }));
  cuerpoAC.position.y = 0.3; ac.add(cuerpoAC);
  const aspas = new THREE.Group(); aspas.position.set(0.26, 0.3, 0);
  for (let k = 0; k < 3; k++) {
    const b = new THREE.Mesh(new THREE.BoxGeometry(0.01, 0.22, 0.05), mEstruct); b.rotation.x = (k * Math.PI * 2) / 3;
    b.position.set(0, 0, 0); b.geometry.translate(0, 0.11, 0); aspas.add(b);
  }
  const luzAC = new THREE.Mesh(new THREE.SphereGeometry(0.04, 8, 8), new THREE.MeshBasicMaterial({ color: 0x333333 }));
  luzAC.position.set(0.26, 0.52, 0.3);
  ac.add(aspas, luzAC);
  ac.scale.setScalar(0.8); ac.position.set(limites.maxX + 0.35, 0, limites.minZ + 0.8); g.add(ac);

  const bat = new THREE.Group();
  const caja = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.9, 1.1), new THREE.MeshStandardMaterial({ color: 0x2c3a36, roughness: 0.6 }));
  caja.position.y = 0.45; bat.add(caja);
  const hueco = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.76, 0.16), new THREE.MeshBasicMaterial({ color: 0x0a0f0d }));
  hueco.position.set(-0.26, 0.45, 0.3); bat.add(hueco);
  const mBar = new THREE.MeshBasicMaterial({ color: 0x3ecf8e });
  const barra = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.72, 0.12), mBar);
  barra.geometry.translate(0, 0.36, 0); barra.position.set(-0.27, 0.09, 0.3); bat.add(barra);
  bat.position.set(limites.minX - 0.45, 0, m0.cz); g.add(bat);

  // --- marquesina + poste de parada de bus ---
  if (esCupula && kit === 'parada_bus') {
    const poste = new THREE.Group();
    const tubo = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 2.9, 10), mEstruct); tubo.position.y = 1.45;
    const cv = document.createElement('canvas'); cv.width = cv.height = 128;
    const cg = cv.getContext('2d'); cg.fillStyle = '#d4202a'; cg.fillRect(0, 0, 128, 128);
    cg.fillStyle = '#fff'; cg.font = 'bold 56px system-ui'; cg.textAlign = 'center'; cg.textBaseline = 'middle'; cg.fillText('BUS', 64, 64);
    const letrero = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.45, 0.04), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(cv) }));
    letrero.position.set(0, 2.65, 0);
    const techo = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.05, 0.9), mEstruct); techo.position.set(-0.7, 2.5, -0.1);
    poste.add(tubo, letrero, techo);
    poste.position.set(limites.minX - 0.7, 0, 0.9); poste.rotation.y = Math.PI; g.add(poste);
  }

  // --- modelos 3D opcionales (asíncronos; 404 -> se queda lo procedural) ---
  let vivo = true;
  cargarGLB('banco').then(base => {
    if (!base || !vivo) return;
    for (const b of bancos) {
      const mod = colocarModelo(base, { largo: 2.0, giroY: b.lado > 0 ? 0 : Math.PI });
      mod.position.set(b.x, 0, b.z); b.banco.visible = false; g.add(mod);
    }
  });
  if (esCupula) cargarGLB('jardin').then(base => {
    if (!base || !vivo) return;
    for (let c = 0; c < cols; c++) {
      const L = filasCol[c] * LADO, cx = (c - (cols - 1) / 2) * LADO;
      const mod = colocarModelo(base, { alto: 1.8 });
      mod.position.set(cx, 0, -L + 0.45); g.add(mod);
    }
  });
  // --- árbol solar: el árbol del modelo (o tronco procedural) con una copa de placas FV encima ---
  const verArbol = tipo === 'arbol_solar' || (esCupula && conArbol);
  const arbol = new THREE.Group(); arbol.visible = verArbol;
  if (tipo === 'arbol_solar') arbol.position.set(0, 0, -3); else arbol.position.set(limites.maxX + 3.2, 0, limites.minZ + 1.5);
  g.add(arbol);
  const ALTO_ARBOL = 3.6;
  const troncoProc = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.3, ALTO_ARBOL, 12), new THREE.MeshStandardMaterial({ color: 0x5a4632, roughness: 0.9 }));
  troncoProc.position.y = ALTO_ARBOL / 2; arbol.add(troncoProc);
  const copaFV = new THREE.Group(); copaFV.position.y = ALTO_ARBOL + 0.45; arbol.add(copaFV);
  const mFVarbol = new THREE.MeshStandardMaterial({ map: texFV(1, 1), roughness: 0.3, metalness: 0.5, emissive: 0x3a7bff, emissiveIntensity: 0 });
  mFV.push(mFVarbol);
  const eje = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.5, 8), mEstruct); eje.position.y = -0.25; copaFV.add(eje);
  for (let i = 0; i < 6; i++) {          // 6 «pétalos» de 1,6 x 1 m inclinados 15° hacia fuera
    const a = i / 6 * Math.PI * 2, brazo = new THREE.Group(); brazo.rotation.y = a;
    const pan = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.04, 1.6), mFVarbol); pan.position.set(0, 0, 1.0); pan.rotation.x = 0.26;
    const barra = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.04, 1.8), mEstruct); barra.position.set(0, -0.05, 0.9);
    brazo.add(pan, barra); copaFV.add(brazo);
  }
  if (verArbol) cargarGLB('parada').then(base => {
    if (!base || !vivo) return;
    const mod = colocarModelo(base, { alto: ALTO_ARBOL + 0.2 });
    mod.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    troncoProc.visible = false; arbol.add(mod);
    const caja = new THREE.Box3().setFromObject(mod), tam = caja.getSize(new THREE.Vector3());
    copaFV.position.y = caja.max.y - arbol.position.y + 0.35;           // placas por ENCIMA de la copa
    copaFV.scale.setScalar(Math.max(1, Math.max(tam.x, tam.z) / 4.4));   // cubren todo el ancho de la copa
  });

  // --- tipos sin bóveda: plataforma, pérgolas FV, jardines, banco de piedra ---
  const extrasUpd = [];
  function pergolaFV(x, z, w, d, h) {
    const pg = new THREE.Group(); pg.position.set(x, 0, z);
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
      const pil = new THREE.Mesh(new THREE.BoxGeometry(0.1, h, 0.1), mEstruct); pil.position.set(sx * (w / 2 - 0.1), h / 2, sz * (d / 2 - 0.1)); pg.add(pil);
    }
    const mat = new THREE.MeshStandardMaterial({ map: texFV(Math.round(w), Math.round(d)), roughness: 0.3, metalness: 0.5, emissive: 0x3a7bff, emissiveIntensity: 0 });
    mFV.push(mat);
    const techo = new THREE.Mesh(new THREE.BoxGeometry(w, 0.06, d), mat); techo.position.y = h; techo.rotation.x = -0.08; pg.add(techo);
    const marco = new THREE.Mesh(new THREE.BoxGeometry(w + 0.1, 0.05, d + 0.1), mEstruct); marco.position.y = h - 0.06; marco.rotation.x = -0.08; pg.add(marco);
    g.add(pg);
    for (let k = 0; k < 4; k++) toberasNeb.push({ x: x + (k / 3 - 0.5) * (w - 0.6), z, y: h - 0.15 });
    return pg;
  }
  if (!esCupula) {
    const plat = new THREE.Mesh(new THREE.CylinderGeometry(3.4, 3.4, 0.1, 48), mSuelo); plat.position.set(0, -0.05, -3); plat.receiveShadow = true; g.add(plat);
  }
  if (tipo === 'arbol_solar') {
    // el árbol nebuliza agua desde el borde de la copa (más fresco bajo las placas)
    for (let k = 0; k < 8; k++) { const a = k / 8 * Math.PI * 2; toberasNeb.push({ x: Math.cos(a) * 1.6, z: -3 + Math.sin(a) * 1.6, y: ALTO_ARBOL - 0.2 }); }
  }
  if (tipo === 'jardin') {
    pergolaFV(0, -3, 5.4, 3.6, 2.8);
    const sitios = [[-2.1, -4.6, 0.3], [0, -5.0, 0], [2.1, -4.6, -0.3]];
    cargarGLB('jardin').then(base => {
      if (!base || !vivo) return;
      for (const [x, z, r] of sitios) { const m = colocarModelo(base, { alto: 2.3, giroY: r }); m.position.set(x, 0, z); g.add(m); }
    });
    for (const [x, z] of sitios) {   // macetero procedural (también sin GLB)
      const mac = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.45, 0.4, 16), mMacetero); mac.position.set(x, 0.2, z + 0.7); g.add(mac);
      for (let k = 0; k < 3; k++) { const pl = new THREE.Mesh(new THREE.SphereGeometry(0.22, 10, 8), mVerde[k]); pl.position.set(x + (k - 1) * 0.22, 0.55, z + 0.7); g.add(pl); }
    }
    cargarGLB('banco').then(base => {
      if (!base || !vivo) return;
      for (const sx of [-1.3, 1.3]) { const m = colocarModelo(base, { largo: 2.0, giroY: 0 }); m.position.set(sx, 0, -2.4); m.rotation.y = Math.PI / 2; g.add(m); }
    });
  }
  if (tipo === 'banco_solar') {
    pergolaFV(0, -3, 4.2, 2.4, 2.6);
    const bancoProc = new THREE.Mesh(new THREE.BoxGeometry(3.2, 0.45, 0.6), new THREE.MeshStandardMaterial({ color: 0xa9a59c, roughness: 0.9 }));
    bancoProc.position.set(0, 0.225, -3); g.add(bancoProc);
    cargarGLB('banco').then(base => {
      if (!base || !vivo) return;
      const m = colocarModelo(base, { largo: 3.4 }); m.position.set(0, 0, -3); m.rotation.y = Math.PI / 2; bancoProc.visible = false; g.add(m);
    });
  }
  // fuente de agua potable (procedural; los modelos de 3D Warehouse exigen cuenta)
  function fuente(x, z) {
    const f = new THREE.Group(); f.position.set(x, 0, z);
    const mAcero = new THREE.MeshStandardMaterial({ color: 0xb8c0c4, metalness: 0.85, roughness: 0.3 });
    const pie = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.16, 0.9, 16), mAcero); pie.position.y = 0.45;
    const pila = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.2, 0.12, 24), mAcero); pila.position.y = 0.94;
    const agua = new THREE.Mesh(new THREE.CircleGeometry(0.24, 24), new THREE.MeshStandardMaterial({ color: 0x5ab4e8, roughness: 0.1, metalness: 0.2 }));
    agua.rotation.x = -Math.PI / 2; agua.position.y = 0.995;
    const caño = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.18, 8), mAcero); caño.position.set(0, 1.07, -0.12);
    const base = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.04, 20), mAcero); base.position.y = 0.02;
    f.add(pie, pila, agua, caño, base); g.add(f);
    const ch = crearChorro(60, { color: 0x8fd0ff, size: 0.05, opacity: 0.9, vida: 0.8, grav: 9.8, emitir(p, v, i) {
      p[i] = x; p[i + 1] = 1.16; p[i + 2] = z - 0.12;
      v[i] = (Math.random() - 0.5) * 0.05; v[i + 1] = 1.1 + Math.random() * 0.15; v[i + 2] = 0.55 + Math.random() * 0.08; } });
    g.add(ch.pts); extrasUpd.push(dt => ch.update(dt, true));
  }
  if (esCupula) fuente(limites.minX - 0.9, -1.6); else fuente(2.7, -0.8);

  // --- luz interior (noche) ---
  const luzInt = new THREE.PointLight(0xffc27a, 0, 8); luzInt.position.set(0, TOPE - 0.4, (limites.minZ + limites.maxZ) / 2);
  g.add(luzInt);

  // --- partículas ---
  const chorroAC = crearChorro(50 * n, { color: 0x4aa8ff, size: 0.12, opacity: 0.8, vida: 2.2, emitir(p, v, i) {
    const t = toberasAC[Math.floor(Math.random() * toberasAC.length)];
    p[i] = t.x; p[i + 1] = 2.1 + Math.random() * 0.2; p[i + 2] = t.z + (Math.random() - 0.5) * 1.2;
    v[i] = t.dir * (0.4 + Math.random() * 0.3); v[i + 1] = -0.15 - Math.random() * 0.15; v[i + 2] = (Math.random() - 0.5) * 0.1; } });
  const chorroNeb = crearChorro(70 * n, { color: 0xffffff, size: 0.3, opacity: 0.35, vida: 3, emitir(p, v, i) {
    const t = toberasNeb[Math.floor(Math.random() * toberasNeb.length)];
    p[i] = t.x + (Math.random() - 0.5) * 0.8; p[i + 1] = t.y ?? TOPE - 0.25; p[i + 2] = t.z + (Math.random() - 0.5) * 1.6;
    v[i] = (Math.random() - 0.5) * 0.15; v[i + 1] = -0.25 - Math.random() * 0.15; v[i + 2] = (Math.random() - 0.5) * 0.15; } });
  g.add(chorroAC.pts, chorroNeb.pts);

  // --- personas ---
  const avatares = new Map();   // clave -> {grupo, cuerpo, etiqueta, mat, objetivo, rotX, escY}
  const mats = { normal: 0x5aa9e6, rojo: 0xff2a2a };
  let desmayo = { activo: false, persona: null };
  const anillo = new THREE.Mesh(new THREE.RingGeometry(0.4, 0.55, 40), new THREE.MeshBasicMaterial({ color: 0xff2a2a, transparent: true, opacity: 0.8, side: THREE.DoubleSide, depthWrite: false }));
  anillo.rotation.x = -Math.PI / 2; anillo.position.y = 0.03; anillo.visible = false; g.add(anillo);

  function crearAvatar(clave, p, idx) {
    const grupo = new THREE.Group();
    const r = aleatorio(1 + (Number(p.id) || idx) * 7919);
    const mat = new THREE.MeshStandardMaterial({ color: ROPA[Math.floor(r() * ROPA.length)], roughness: 0.75, emissive: 0x000000 });
    const mPiel = new THREE.MeshStandardMaterial({ color: PIEL[Math.floor(r() * PIEL.length)], roughness: 0.7 });
    const mPant = new THREE.MeshStandardMaterial({ color: r() < 0.5 ? 0x2b3a55 : 0x55504a, roughness: 0.85 });
    const mPelo = new THREE.MeshStandardMaterial({ color: PELO[Math.floor(r() * PELO.length)], roughness: 0.9 });
    const alto = 1.6 + r() * 0.25, k = alto / 1.75;
    const dorso = new THREE.Group();
    const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.17, 0.42, 4, 12), mat); torso.position.y = 1.2; torso.scale.set(1, 1, 0.7);
    const cuello = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.08, 8), mPiel); cuello.position.y = 1.5;
    const cabeza = new THREE.Mesh(new THREE.SphereGeometry(0.11, 18, 14), mPiel); cabeza.position.y = 1.62; cabeza.scale.set(0.9, 1.05, 0.95);
    const pelo = new THREE.Mesh(new THREE.SphereGeometry(0.115, 18, 10, 0, Math.PI * 2, 0, Math.PI * 0.55), mPelo); pelo.position.y = 1.64;
    const brazos = [-1, 1].map(sx => { const b = new THREE.Mesh(new THREE.CapsuleGeometry(0.05, 0.5, 4, 8), mat);
      b.position.set(sx * 0.23, 1.15, 0); b.rotation.z = sx * 0.08; return b; });
    const manos = [-1, 1].map(sx => { const m = new THREE.Mesh(new THREE.SphereGeometry(0.05, 8, 6), mPiel); m.position.set(sx * 0.25, 0.85, 0); return m; });
    const piernas = [-1, 1].map(sx => { const l = new THREE.Mesh(new THREE.CapsuleGeometry(0.07, 0.72, 4, 8), mPant);
      l.position.set(sx * 0.09, 0.46, 0); return l; });
    const pies = [-1, 1].map(sx => { const f = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.06, 0.24), mPelo); f.position.set(sx * 0.09, 0.03, 0.04); return f; });
    const proc = new THREE.Group(); proc.add(torso, cuello, cabeza, pelo, ...brazos, ...manos, ...piernas, ...pies);
    dorso.add(proc);
    dorso.scale.setScalar(k);
    dorso.traverse(o => { if (o.isMesh) o.castShadow = true; });
    grupo.add(dorso);
    grupo.rotation.y = r() * Math.PI * 2;
    const etiqueta = crearEtiqueta(`Persona ${p.id ?? idx + 1}`); etiqueta.position.set(0, 2.05, 0); etiqueta.visible = etiquetas;
    grupo.add(etiqueta);
    g.add(grupo);
    const a = { grupo, dorso, proc, mat, k, etiqueta, objetivo: new THREE.Vector3(), rotX: 0, escY: 1, nuevo: true, id: p.id,
      base: mat.color.getHex(), rig: null, posado: null };
    if (personaBase) ponerRig(a);
    return a;
  }
  let personaBase = null;
  function ponerRig(a) {
    a.rig = nuevoRig(personaBase, 0.93);   // modelo 1,83 m -> 1,70 m (dorso escala ±7 %)
    a.dorso.add(a.rig.raiz); a.proc.visible = false; a.posado = null;
  }
  cargarGLB('persona').then(base => {
    if (!base || !vivo) return;
    personaBase = base;
    for (const a of avatares.values()) ponerRig(a);
  });
  const clampX = x => Math.max(limites.minX + 0.3, Math.min(limites.maxX - 0.3, x));
  const clampZ = z => Math.max(limites.minZ + 0.3, Math.min(limites.maxZ - 0.3, z));

  // --- estado y animación ---
  const est = { claraboya: 0, ac: false, nebulizador: false, ventilador: false, temp: null, solar: 0, bateria: 0, noche: false };
  let clarActual = 0;
  const colAire = new THREE.Color(0x9fd8c0), colObj = new THREE.Color();
  const wMax = n * 800;   // W pico estimados (4 m² FV x ~200 W/m² por módulo)
  let tiempo = 0;

  const api = {
    group: g, kit, n, limites, modulos,
    centro: new THREE.Vector3((limites.minX + limites.maxX) / 2, 1, (limites.minZ + limites.maxZ) / 2),
    set(s) {
      Object.assign(est, s);
      if ('bateria' in s) {
        const f = Math.max(0, Math.min(1, (s.bateria ?? 0) / 100));
        barra.scale.y = Math.max(f, 0.001);
        mBar.color.set(f < 0.2 ? 0xff5c5c : f < 0.5 ? 0xf5b942 : 0x3ecf8e);
      }
      if ('noche' in s) luzInt.intensity = s.noche ? 2.2 : 0;
    },
    setPersonas(lista) {
      const vistos = new Set();
      (lista || []).forEach((p, idx) => {
        if (p.x == null || p.y == null) return;
        const clave = p.id ?? `i${idx}`;
        vistos.add(clave);
        let a = avatares.get(clave);
        if (!a) { a = crearAvatar(clave, p, idx); avatares.set(clave, a); }
        a.objetivo.set(clampX(p.x), 0, clampZ(-p.y));
        a.estado = p.estado || 'de_pie';
        if (a.nuevo) { a.grupo.position.copy(a.objetivo); a.nuevo = false; }
      });
      for (const [k, a] of avatares) if (!vistos.has(k)) {
        g.remove(a.grupo); a.grupo.traverse(o => { o.geometry?.dispose(); o.material?.map?.dispose(); o.material?.dispose?.(); });
        avatares.delete(k);
      }
    },
    setDesmayo(d) { desmayo = { activo: !!d?.activo, persona: d?.persona ?? null }; },
    actualizar(dt) {
      tiempo += dt;
      const k = 1 - Math.exp(-dt * 3);
      // claraboya
      clarActual += (est.claraboya - clarActual) * k;
      for (const p of claraboyas) p.rotation.z = clarActual * 1.1;
      // tinte del aire
      colObj.set(colorTemp(est.temp)); colAire.lerp(colObj, k); mAire.color.copy(colAire);
      // placas
      const f = Math.max(0, Math.min(1, (est.solar || 0) / wMax));
      for (const m of mFV) m.emissiveIntensity = f * 1.4;
      // AC / ventilador
      luzAC.material.color.set(est.ac ? 0x4aa8ff : 0x333333);
      if (est.ventilador || est.ac) aspas.rotation.x += dt * 14;
      chorroAC.update(dt, !!est.ac);
      chorroNeb.update(dt, !!est.nebulizador);
      for (const f of extrasUpd) f(dt);
      // personas
      let objetivoDesm = null;
      if (desmayo.activo) {
        objetivoDesm = avatares.get(desmayo.persona) ?? [...avatares.values()].find(a => a.estado === 'suelo') ?? avatares.values().next().value ?? null;
      }
      for (const a of avatares.values()) {
        a.grupo.position.lerp(a.objetivo, k);
        const suelo = a.estado === 'suelo', sentado = a.estado === 'sentado';
        a.rotX += ((suelo ? -Math.PI / 2 : 0) - a.rotX) * k;
        a.dorso.rotation.x = a.rotX;
        if (a.rig) {
          if (a.posado !== a.estado) { posar(a.rig, sentado ? 'sentado' : 'de_pie'); a.posado = a.estado; }
          a.dorso.position.y = suelo ? 0.12 : sentado ? -0.42 : 0;
        } else {
          a.escY += ((sentado ? 0.65 : 1) - a.escY) * k;
          a.dorso.scale.y = a.escY * a.k;
          a.dorso.position.y = suelo ? 0.15 : sentado ? 0.12 : 0;
        }
        a.etiqueta.position.y = suelo ? 0.7 : sentado ? 1.5 : 2.05;
        const rojo = a === objetivoDesm;
        a.mat.color.set(rojo ? mats.rojo : a.base);
        if (a.rig) for (const m of a.rig.mats) { m.emissive?.set(rojo ? 0xff0000 : 0x000000); if (m.emissive) m.emissiveIntensity = rojo ? 0.5 + 0.4 * Math.sin(tiempo * 8) : 0; }
        a.mat.emissive.set(rojo ? 0xff0000 : 0x000000);
        a.mat.emissiveIntensity = rojo ? 0.4 + 0.4 * Math.sin(tiempo * 8) : 0;
      }
      anillo.visible = !!objetivoDesm;
      if (objetivoDesm) {
        anillo.position.x = objetivoDesm.grupo.position.x; anillo.position.z = objetivoDesm.grupo.position.z;
        const s = 1 + 0.5 * ((tiempo * 1.6) % 1);
        anillo.scale.set(s, s, 1); anillo.material.opacity = 0.9 - 0.7 * ((tiempo * 1.6) % 1);
      }
    },
    dispose() {
      vivo = false;
      scene.remove(g);
      g.traverse(o => { o.geometry?.dispose();
        const ms = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
        ms.forEach(m => { m.map?.dispose(); m.dispose(); }); });
    },
  };
  g.traverse(o => { if (o.isMesh && o.material !== mVidrio && o.material !== mAire) { o.castShadow = true; o.receiveShadow = true; } });
  scene.add(g);
  return api;
}
