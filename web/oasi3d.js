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
            if (emitir(pos, vel, i * 3) === false) { life[i] = 0; continue; }   // sin toberas: no emite
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
  persona: 'modelos/persona.glb',
  hiedra: 'modelos/hiedra.glb',
  fuente: 'modelos/fuente.glb',     // «Drinking Fountain» (MooKorea, CC-BY 4.0)     // «Ivy And Vines» (_JooL_, CC-BY 4.0)   // «An Elderly Man» (BELAZ, CC-BY 4.0), rig Mixamo; ver modelos/CREDITOS.md
};
const _glb = {};
function cargarGLB(clave) {
  if (new URLSearchParams(globalThis.location?.search || '').has('sin_modelos')) return Promise.resolve(null);
  return (_glb[clave] ??= new Promise(res => {
    new GLTFLoader().load(MODELOS[clave], gltf => {
      gltf.scene.traverse(o => { if (o.isMesh) o.userData.compartido = true; });   // no liberar al reconstruir
      res(gltf.scene);
    }, undefined, () => res(null));
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
                                          cubierta = 'vidrio_control_solar', etiquetas = true, tipo = 'cupula',
                                          largo = null, ancho = 2.4 } = {}) {
  // tipo: 'cupula' (módulos con bóveda) | 'marquesina' (parada bioclimática 6 x 2,2 m) | 'arbol_solar' | 'jardin' | 'banco_solar'
  const esCupula = tipo === 'cupula';
  // pabellón: largo 4–12 m (o por módulos 1/2/3 -> 4/6/8 m) y ancho 2,4 / 3,6 / 4,8 m
  const LP = tipo === 'pabellon' ? (largo ?? 2 * (Math.max(1, Math.min(3, Math.round(n))) + 1)) : 0;
  const WP = Math.max(2.4, Math.min(4.8, ancho || 2.4)), HWP = WP / 2, ZP = -(HWP + 0.2);
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
                           : tipo === 'marquesina' ? { minX: -2.9, maxX: 2.9, minZ: -2.1, maxZ: 0 }
                           : tipo === 'pabellon' ? { minX: -LP / 2 + 0.3, maxX: LP / 2 - 0.3, minZ: ZP - HWP + 0.3, maxZ: ZP + HWP - 0.3 }
                           : tipo === 'pergola' ? { minX: -3.0, maxX: 3.0, minZ: -4.4, maxZ: -0.5 }
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
  ac.scale.setScalar(0.8);
  if (tipo === 'marquesina') ac.position.set(4.3, 0, -1.9);
  else if (tipo === 'pabellon') ac.position.set(LP / 2 + 1.2, 0, ZP - HWP);
  else if (tipo === 'pergola') ac.position.set(3.7, 0, -4.9); else ac.position.set(limites.maxX + 0.35, 0, limites.minZ + 0.8);
  g.add(ac);

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
  // --- enredaderas en los laterales abiertos de la bóveda (sombra + frescor). Entrada libre en el frente ---
  if (esCupula) cargarGLB('hiedra').then(base => {
    if (!base || !vivo) return;
    for (let c = 0; c < cols; c++) {
      const L = filasCol[c] * LADO, cx = (c - (cols - 1) / 2) * LADO;
      for (const sx of (cols === 2 ? [c === 0 ? -1 : 1] : [-1, 1])) {      // en rejilla, solo los lados exteriores
        // copias del panel de hiedra, cara paralela al lateral, altura = pilares
        // la celosía (malla pequeña) marca el ancho de cada copia; las hojas desbordan y se solapan
        const enr = base.clone(true); enr.updateMatrixWorld(true);
        const cajas = [];
        enr.traverse(o => { if (o.isMesh) cajas.push(new THREE.Box3().setFromObject(o)); });
        const celo = cajas.reduce((a, b) => (b.getSize(_v1).x < a.getSize(_v2).x ? b : a));
        const csz = celo.getSize(new THREE.Vector3()), cctr = celo.getCenter(new THREE.Vector3());
        const k = (BASE + 0.15) / csz.y, ancho = csz.x * k;
        const largo = L - 1.2, nCop = Math.max(1, Math.round(largo / ancho));
        for (let q = 0; q < nCop; q++) {
          const m = base.clone(true);
          m.position.set(-cctr.x, -celo.min.y, -cctr.z);          // centro de la celosía en el origen
          const piv = new THREE.Group(); piv.add(m); piv.scale.setScalar(k);
          piv.rotation.y = Math.PI / 2 * (q % 2 ? -1 : 1);       // alterna sentido: hojas hacia los dos lados
          const wrap = new THREE.Group(); wrap.add(piv);
          wrap.position.set(cx + sx * (R + 0.03), 0, -1.2 - (q + 0.5) * (largo / nCop));
          wrap.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
          g.add(wrap);
        }
      }
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
  if (!esCupula && !['marquesina', 'pabellon', 'pergola'].includes(tipo)) {
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
    cargarGLB('fuente').then(b => {   // modelo realista: sustituye a la procedural (el chorro se mantiene)
      if (!b || !vivo) return;
      const m = colocarModelo(b, { alto: 1.0 }); m.position.set(x, 0, z);
      m.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
      for (const o of [pie, pila, agua, caño, base]) o.visible = false; g.add(m);
    });
    const ch = crearChorro(60, { color: 0x8fd0ff, size: 0.05, opacity: 0.9, vida: 0.8, grav: 9.8, emitir(p, v, i) {
      p[i] = x; p[i + 1] = 1.16; p[i + 2] = z - 0.12;
      v[i] = (Math.random() - 0.5) * 0.05; v[i + 1] = 1.1 + Math.random() * 0.15; v[i + 2] = 0.55 + Math.random() * 0.08; } });
    g.add(ch.pts); extrasUpd.push(dt => ch.update(dt, true));
  }
  if (tipo === 'marquesina') {
    // Parada bioclimática (diseño del equipo): vidrio con enredaderas, techo solar con cámara de aire,
    // huecos abajo/arriba para el efecto chimenea, cámara IA y rociadores que se activan con personas.
    const Z = -1.1;                                   // centro en profundidad (frente abierto en z = 0)
    const bx = (w, h, d, m, x, y, z) => { const o = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
      o.position.set(x, y, z + Z); o.castShadow = o.receiveShadow = true; g.add(o); return o; };
    const cil = (r, h, m, x, y, z) => { const o = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, 12), m);
      o.position.set(x, y, z + Z); o.castShadow = true; g.add(o); return o; };
    const mCristal = new THREE.MeshPhysicalMaterial({ color: 0xbfe8f0, transparent: true, opacity: 0.26, roughness: 0.05, side: THREE.DoubleSide, depthWrite: false });
    const mMadera = new THREE.MeshStandardMaterial({ color: 0x9a6b3f, roughness: 0.7 });
    bx(9, 0.15, 5, new THREE.MeshStandardMaterial({ color: 0xb9bdb8, roughness: 0.9 }), 0, -0.04, 0.3);
    [-3, -1, 1, 3].forEach(x => bx(0.08, 2.75, 0.08, mEstruct, x, 1.375, -1.1));
    [-3, 3].forEach(x => bx(0.08, 2.75, 0.08, mEstruct, x, 1.375, 1.1));
    bx(6.2, 0.1, 2.6, mEstruct, 0, 2.78, 0.1);
    bx(6, 2.2, 0.03, mCristal, 0, 1.4, -1.1);                     // hueco abajo y arriba: circula el aire
    [-3, 3].forEach(x => bx(0.03, 2.2, 2.2, mCristal, x, 1.4, 0));
    [-2, 0, 2].forEach(x => bx(0.04, 2.2, 0.05, mEstruct, x, 1.4, -1.1));
    const mSol = new THREE.MeshStandardMaterial({ map: texFV(3, 4), roughness: 0.25, metalness: 0.5, emissive: 0x3a7bff, emissiveIntensity: 0 });
    mFV.push(mSol);
    [-2, 0, 2].forEach(x => { const p = bx(1.9, 0.06, 2.4, mSol, x, 3.12, 0.1); p.rotation.x = 0.14;
      [-0.9, 0.9].forEach(z => [-0.8, 0.8].forEach(dx => cil(0.025, 0.3, mEstruct, x + dx, 2.95, z * 0.9 + 0.1))); });
    // enredaderas sobre el vidrio + jardineras
    const rnd = aleatorio(7), hojas = [];
    const tira = (x, z, top, len) => { for (let y = top; y > top - len; y -= 0.11) hojas.push([x + (rnd() - 0.5) * 0.08, y, z + (rnd() - 0.5) * 0.08, 0.06 + rnd() * 0.07]); };
    for (let x = -2.9; x <= 2.9; x += 0.2) { tira(x, -1.18, 2.55, 1 + rnd() * 1.4); tira(x + 0.1, -1.02, 2.55, 0.6 + rnd() * 1.1); }
    [-1, 1].forEach(sx => { for (let z = -1; z <= 1; z += 0.25) tira(sx * 3.07, z, 2.55, 0.8 + rnd() * 1.5); });
    for (let x = -3; x <= 3; x += 0.3) tira(x, 1.28, 2.72, 0.2 + rnd() * 0.5);
    const mMac = new THREE.MeshStandardMaterial({ color: 0x5a4636, roughness: 0.9 });
    [[0, -1.3, 5.8, 0.4], [-3.2, 0, 0.4, 2], [3.2, 0, 0.4, 2]].forEach(a => bx(a[2], 0.4, a[3], mMac, a[0], 0.2, a[1]));
    for (let i = 0; i < 150; i++) { const r = rnd(), q = Math.floor(rnd() * 3);
      const pp = q === 0 ? [(r - 0.5) * 5.6, 0.45 + rnd() * 0.25, -1.3] : [q === 1 ? -3.2 : 3.2, 0.45 + rnd() * 0.25, (r - 0.5) * 1.8];
      hojas.push([pp[0], pp[1], pp[2], 0.1 + rnd() * 0.1]); }
    const inst = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1, 1), new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.9 }), hojas.length);
    inst.castShadow = true;
    const dmy = new THREE.Object3D(), col = new THREE.Color();
    hojas.forEach((h, i) => { dmy.position.set(h[0], h[1], h[2] + Z); dmy.scale.set(h[3] * 1.1, h[3] * 0.8, h[3] * 0.35);   // hoja aplanada
      dmy.rotation.set((rnd() - 0.5) * 1.2, (rnd() - 0.5) * 1.2, rnd() * Math.PI); dmy.updateMatrix(); inst.setMatrixAt(i, dmy.matrix);
      col.setHSL(0.26 + rnd() * 0.08, 0.6, 0.12 + rnd() * 0.12); inst.setColorAt(i, col); });
    g.add(inst);
    // banco y señal
    bx(3.4, 0.06, 0.42, mMadera, 0, 0.5, -0.8); bx(3.4, 0.4, 0.05, mMadera, 0, 0.8, -0.98);
    [-1.5, 1.5].forEach(x => bx(0.05, 0.5, 0.35, mEstruct, x, 0.25, -0.8));
    cil(0.04, 2.6, mEstruct, 3.6, 1.3, 1.2);
    const sc = document.createElement('canvas'); sc.width = sc.height = 128; const s2 = sc.getContext('2d');
    s2.fillStyle = '#d9322d'; s2.fillRect(0, 0, 128, 128); s2.fillStyle = '#fff'; s2.font = 'bold 56px sans-serif'; s2.textAlign = 'center'; s2.fillText('BUS', 64, 82);
    bx(0.5, 0.5, 0.03, new THREE.MeshStandardMaterial({ map: new THREE.CanvasTexture(sc) }), 3.6, 2.35, 1.2);
    // cámara IA + campo de visión (verde con personas dentro)
    const domo = new THREE.Mesh(new THREE.SphereGeometry(0.12, 16, 8, 0, Math.PI * 2, Math.PI / 2), new THREE.MeshStandardMaterial({ color: 0x111111, metalness: 0.8 }));
    domo.rotation.x = Math.PI; domo.position.set(0, 2.73, 0.3 + Z); g.add(domo);
    const led = new THREE.Mesh(new THREE.SphereGeometry(0.03, 8, 8), new THREE.MeshBasicMaterial({ color: 0xff3b30 })); led.position.set(0.1, 2.68, 0.3 + Z); g.add(led);
    const fov = new THREE.Mesh(new THREE.ConeGeometry(1.5, 2.5, 32, 1, true), new THREE.MeshBasicMaterial({ color: 0xffcc33, transparent: true, opacity: 0.07, side: THREE.DoubleSide, depthWrite: false }));
    fov.position.set(0, 1.45, 0.3 + Z); g.add(fov);
    // tubería y 8 boquillas de nebulización (las usa el chorro del nebulizador)
    cil(0.02, 5.4, mEstruct, 0, 2.68, 0.95).rotation.z = Math.PI / 2;
    for (let i = 0; i < 8; i++) { const x = -2.45 + i * 0.7; cil(0.025, 0.07, new THREE.MeshStandardMaterial({ color: 0xc0c8cc, metalness: 0.9 }), x, 2.64, 0.95);
      toberasNeb.push({ x, z: 0.95 + Z, y: 2.6 }); }
    // corriente de aire (efecto chimenea): entra abajo por detrás, sale por la cámara del techo
    const NA = 140, ag = new THREE.BufferGeometry(); ag.setAttribute('position', new THREE.BufferAttribute(new Float32Array(NA * 3), 3));
    const aire = new THREE.Points(ag, new THREE.PointsMaterial({ color: 0x2d9cff, size: 0.08, transparent: true, opacity: 0.9, depthWrite: false }));
    aire.frustumCulled = false; g.add(aire);
    const aph = Array.from({ length: NA }, () => [rnd(), -2.9 + rnd() * 5.8, (rnd() - 0.5) * 0.7]);
    const bez = (a, b, c, t) => (1 - t) * (1 - t) * a + 2 * (1 - t) * t * b + t * t * c;
    let T = 0;
    extrasUpd.push(dt => {
      T += dt;
      const fluye = est.ventilador || est.claraboya > 0 || !est.ac;   // ventilación pasiva salvo con AC cerrado
      aire.visible = fluye;
      if (fluye) { const a = ag.attributes.position;
        for (let i = 0; i < NA; i++) { const q = aph[i], t = (q[0] + T * 0.12) % 1;
          a.setXYZ(i, q[1] + Math.sin(t * 6 + i) * 0.05, bez(0.3, 0.6, 3.35, t), bez(-1.7, -0.2, 0.5, t) + q[2] * 0.3 + Z); }
        a.needsUpdate = true; }
      const hay = avatares.size > 0;
      led.material.color.set(hay ? 0x2eff7a : 0xff3b30);
      fov.material.color.set(hay ? 0x2eff7a : 0xffcc33); fov.material.opacity = hay ? 0.14 : 0.07;
    });
  }
  if (tipo === 'pabellon') {
    // Pabellón Venturi (diseño del equipo): vidrio y enredaderas, techo semicircular con garganta
    // Venturi en la cima, rejillas bajas/altas, extractores y puertas ENTRADA/SALIDA. Ampliable a lo
    // largo (L) y a lo ancho (W, el radio del techo crece con él). Las animaciones de aire usan la
    // física del simulador (evento `fisica`, sim/fisica_pabellon.py) si llega; si no, valores típicos.
    const L = LP, W = WP, HW = HWP, Z = ZP, mm = Math.max(1, Math.round(L / 2));
    const Rr = HW + 0.15, K_CIMA = 1.6;
    const bx = (w, h, d, m, x, y, z) => { const o = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
      o.position.set(x, y, z + Z); o.castShadow = o.receiveShadow = true; g.add(o); return o; };
    const cil = (r, h, m, x, y, z) => { const o = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, 12), m);
      o.position.set(x, y, z + Z); o.castShadow = true; g.add(o); return o; };
    const mCristal = new THREE.MeshPhysicalMaterial({ color: 0xbfe8f0, transparent: true, opacity: 0.26, roughness: 0.05, side: THREE.DoubleSide, depthWrite: false });
    const mPuerta = new THREE.MeshPhysicalMaterial({ color: 0x9fd8e6, transparent: true, opacity: 0.4, roughness: 0.05, side: THREE.DoubleSide, depthWrite: false });
    const mMadera = new THREE.MeshStandardMaterial({ color: 0x9a6b3f, roughness: 0.7 });
    const rotulo = (txt, bg) => { const c = document.createElement('canvas'); c.width = 256; c.height = 72; const x = c.getContext('2d');
      x.fillStyle = bg; x.fillRect(0, 0, 256, 72); x.fillStyle = '#fff'; x.font = 'bold 34px sans-serif'; x.textAlign = 'center'; x.fillText(txt, 128, 48); return new THREE.CanvasTexture(c); };
    bx(L + 3, 0.15, W + 2.6, new THREE.MeshStandardMaterial({ color: 0xb9bdb8, roughness: 0.9 }), 0, -0.04, 0.3);
    bx(L, 0.04, W, new THREE.MeshStandardMaterial({ color: 0x8a8f86 }), 0, 0.05, 0);
    for (let k = 0; k <= mm; k++) [-HW, HW].forEach(z => bx(0.08, 2.75, 0.08, mEstruct, -L / 2 + k * L / mm, 1.375, z));
    // techo semicircular con garganta en la cima (dos medias bóvedas separadas)
    const s0 = 0.11 / Rr * 1.35, mTecho = new THREE.MeshStandardMaterial({ color: 0xe6ecee, metalness: 0.3, roughness: 0.5, side: THREE.DoubleSide });
    const casco = (a0, a1, r, mat, len, x) => { const o = new THREE.Mesh(new THREE.CylinderGeometry(r, r, len || L + 0.3, 64, 1, true, a0, a1 - a0), mat);
      o.rotation.z = Math.PI / 2; o.position.set(x || 0, 2.75, Z); o.castShadow = o.receiveShadow = true; g.add(o); return o; };
    casco(0, Math.PI / 2 - s0, Rr, mTecho); casco(Math.PI / 2 + s0, Math.PI, Rr, mTecho);
    for (let k = 0; k <= mm; k++) { const ar = new THREE.Mesh(new THREE.TorusGeometry(Rr, 0.025, 6, 32, Math.PI), mEstruct);
      ar.rotation.y = Math.PI / 2; ar.position.set(-L / 2 + k * L / mm, 2.75, Z); g.add(ar); }
    [-1, 1].forEach(sx => { const e = new THREE.Mesh(new THREE.CircleGeometry(Rr, 32, 0, Math.PI), mCristal);
      e.rotation.y = sx * Math.PI / 2; e.position.set(sx * L / 2, 2.75, Z); g.add(e); });
    const yc = 2.75 + Rr;                                       // cota de la garganta
    const deflector = (zc, y, len, ang) => { const o = bx(L - 0.1, 0.02, len, mEstruct, 0, y, zc); o.rotation.x = ang; };
    deflector(0.345, yc + 0.35 * Rr / 1.35, 0.52, -0.63); deflector(-0.345, yc + 0.35 * Rr / 1.35, 0.52, 0.63);
    // compuertas de la garganta: las abre el control («claraboya» 0..1) -> regulan la succión Venturi
    const compuertas = [-1, 1].map(sz => { const piv = new THREE.Group(); piv.position.set(0, yc - 0.02, Z + sz * 0.13); g.add(piv);
      const hoja = new THREE.Mesh(new THREE.BoxGeometry(L - 0.2, 0.02, 0.26), mEstruct); hoja.position.z = -sz * 0.13; piv.add(hoja);
      hoja.castShadow = true; return { piv, sz }; });
    [-HW, HW].forEach(z => bx(L, 2.2, 0.03, mCristal, 0, 1.4, z));
    // extremos con puerta (ENTRADA a -x, SALIDA a +x)
    const puertas = [];
    [-1, 1].forEach(sx => { const x = sx * L / 2, lat = (W - 1.1) / 2;
      [-1, 1].forEach(q => bx(0.03, 2.2, lat, mCristal, x, 1.4, q * (0.55 + lat / 2)));
      bx(0.03, 0.35, 1.1, mCristal, x, 2.325, 0); bx(0.05, 0.05, 1.2, mEstruct, x, 2.15, 0);
      [-0.55, 0.55].forEach(z => bx(0.05, 2.15, 0.05, mEstruct, x, 1.075, z));
      const hoja = new THREE.Group(); hoja.position.set(x + sx * 0.05, 0, Z); g.add(hoja);
      const vid = new THREE.Mesh(new THREE.BoxGeometry(0.03, 2.1, 1.08), mPuerta); vid.position.y = 1.08; hoja.add(vid);
      [-0.53, 0.53].forEach(z => { const b = new THREE.Mesh(new THREE.BoxGeometry(0.05, 2.1, 0.04), mEstruct); b.position.set(0, 1.08, z); hoja.add(b); });
      puertas.push({ m: hoja, x, o: 0 });
      const sg = new THREE.Mesh(new THREE.PlaneGeometry(0.95, 0.27), new THREE.MeshBasicMaterial({ map: rotulo(sx < 0 ? 'ENTRADA' : 'SALIDA', sx < 0 ? '#1f8f4e' : '#c2371f') }));
      sg.position.set(x + sx * 0.07, 2.62, Z); sg.rotation.y = sx * Math.PI / 2; g.add(sg); });
    // placas FV curvas sobre el techo (2 franjas de 1,05 rad)
    for (let i = 0; i < mm; i++) { const x = -L / 2 + (i + 0.5) * L / mm, w = L / mm - 0.1;
      const mat = new THREE.MeshStandardMaterial({ map: texFV(2, 2), roughness: 0.25, metalness: 0.5, emissive: 0x3a7bff, emissiveIntensity: 0, side: THREE.DoubleSide });
      mFV.push(mat); [[0.25, 1.3], [Math.PI - 1.3, Math.PI - 0.25]].forEach(a2 => casco(a2[0], a2[1], Rr + 0.03, mat, w, x)); }
    // enredaderas + jardineras
    const rnd = aleatorio(7), hojas = [];
    const tira = (x, z, top, len) => { for (let y = top; y > top - len; y -= 0.11) hojas.push([x + (rnd() - 0.5) * 0.08, y, z + (rnd() - 0.5) * 0.08, 0.06 + rnd() * 0.07]); };
    for (let x = -L / 2 + 0.1; x <= L / 2 - 0.1; x += 0.2) { tira(x, -HW - 0.1, 2.55, 1 + rnd() * 1.4); tira(x + 0.1, -HW + 0.08, 2.55, 0.6 + rnd() * 1.1); }
    for (let x = -L / 2 + 0.2; x <= L / 2 - 0.2; x += 0.35) tira(x, HW + 0.1, 2.55, 0.5 + rnd() * 0.9);
    [-1, 1].forEach(sx => [-1, 1].forEach(q => { for (let z = 0.65; z <= HW - 0.05; z += 0.2) tira(sx * (L / 2 + 0.05), q * z, 2.55, 0.8 + rnd() * 1.5); }));
    const mMac = new THREE.MeshStandardMaterial({ color: 0x5a4636, roughness: 0.9 });
    [-HW - 0.3, HW + 0.3].forEach(z => bx(L - 0.2, 0.4, 0.4, mMac, 0, 0.2, z));
    for (let i = 0; i < L * 28; i++) hojas.push([(rnd() - 0.5) * (L - 0.4), 0.45 + rnd() * 0.25, rnd() < 0.5 ? -HW - 0.3 : HW + 0.3, 0.1 + rnd() * 0.1]);
    const inst = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1, 1), new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.9 }), hojas.length);
    inst.castShadow = true; const dmy = new THREE.Object3D(), col = new THREE.Color();
    hojas.forEach((h, i) => { dmy.position.set(h[0], h[1], h[2] + Z); dmy.scale.set(h[3] * 1.1, h[3] * 0.8, h[3] * 0.35);
      dmy.rotation.set((rnd() - 0.5) * 1.2, (rnd() - 0.5) * 1.2, rnd() * Math.PI); dmy.updateMatrix(); inst.setMatrixAt(i, dmy.matrix);
      col.setHSL(0.26 + rnd() * 0.08, 0.6, 0.12 + rnd() * 0.12); inst.setColorAt(i, col); });
    g.add(inst);
    // bancos interiores (uno por lado si el pabellón es ancho)
    const bl = L - 1.8;
    for (const sz of (W >= 3.6 ? [-1, 1] : [-1])) { const zb = sz * (HW - 0.3), zr = sz * (HW - 0.12);
      bx(bl, 0.06, 0.42, mMadera, 0, 0.5, zb); bx(bl, 0.4, 0.05, mMadera, 0, 0.8, zr);
      [-1, 1].forEach(sx => bx(0.05, 0.5, 0.35, mEstruct, sx * (bl / 2 - 0.1), 0.25, zb)); }
    // cámaras IA
    const camaras = [], nc = Math.max(1, Math.round(L / 3));
    for (let i = 0; i < nc; i++) { const x = -L / 2 + (i + 0.5) * L / nc;
      const domo = new THREE.Mesh(new THREE.SphereGeometry(0.12, 16, 8, 0, Math.PI * 2, Math.PI / 2), new THREE.MeshStandardMaterial({ color: 0x111111, metalness: 0.8 }));
      domo.rotation.x = Math.PI; domo.position.set(x, 2.73, Z); g.add(domo);
      const led = new THREE.Mesh(new THREE.SphereGeometry(0.035, 8, 8), new THREE.MeshBasicMaterial({ color: 0xff3b30 })); led.position.set(x + 0.1, 2.68, Z); g.add(led);
      const fov = new THREE.Mesh(new THREE.ConeGeometry(Math.min(1.4, HW + 0.2), 2.5, 32, 1, true), new THREE.MeshBasicMaterial({ color: 0xffcc33, transparent: true, opacity: 0.07, side: THREE.DoubleSide, depthWrite: false }));
      fov.position.set(x, 1.45, Z); g.add(fov); camaras.push({ x, led, fov }); }
    // tubería y boquillas
    cil(0.02, L - 0.4, mEstruct, 0, 2.68, 0).rotation.z = Math.PI / 2;
    for (let x = -L / 2 + 0.5; x <= L / 2 - 0.4; x += 0.7) { cil(0.025, 0.07, new THREE.MeshStandardMaterial({ color: 0xc0c8cc, metalness: 0.9 }), x, 2.64, 0); toberasNeb.push({ x, z: Z, y: 2.6 }); }
    // rejillas bajas (entrada, azul) y altas (salida, naranja) + extractores en la cima
    const mRej = new THREE.MeshStandardMaterial({ color: 0x3a4548, metalness: 0.6, roughness: 0.4 });
    [-HW, HW].forEach(z => {
      for (let y = 0.04; y < 0.3; y += 0.06) { const o = bx(L - 0.1, 0.012, 0.08, mRej, 0, y, z); o.rotation.x = 0.6 * Math.sign(z); }
      for (let y = 2.52; y < 2.76; y += 0.07) { const o = bx(L - 0.1, 0.012, 0.09, mRej, 0, y, z); o.rotation.x = -0.6 * Math.sign(z); }
      bx(L - 0.1, 0.02, 0.03, new THREE.MeshStandardMaterial({ color: 0x2d9cff }), 0, 0.31, z);
      bx(L - 0.1, 0.02, 0.03, new THREE.MeshStandardMaterial({ color: 0xff8a2b }), 0, 2.5, z); });
    const extract = [];
    for (let k = 0; k < mm; k++) { const x = -L / 2 + (k + 0.5) * L / mm;
      const aro = new THREE.Mesh(new THREE.TorusGeometry(0.26, 0.025, 8, 24), mRej); aro.rotation.x = Math.PI / 2; aro.position.set(x, yc - 0.25, Z); g.add(aro);
      const f = new THREE.Group(); f.position.set(x, yc - 0.25, Z); g.add(f);
      for (let b = 0; b < 5; b++) { const pa = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.01, 0.09), new THREE.MeshStandardMaterial({ color: 0xdfe6e8 }));
        pa.position.x = 0.14; pa.rotation.x = 0.4; const w = new THREE.Group(); w.rotation.y = b * Math.PI * 2 / 5; w.add(pa); f.add(w); }
      extract.push(f); }
    // VIENTO: flujo potencial alrededor del semicilindro (velocidad tangencial 2·v·sinθ en la superficie,
    // atenuada con la distancia); color = velocidad local / viento libre (azul -> amarillo).
    const NW = Math.round(L * 45), wp = new Float32Array(NW * 3), wc = new Float32Array(NW * 3), wz = [], wx = [], wh = [];
    const ZW = 3 * Rr + 1.5;
    for (let i = 0; i < NW; i++) { wz.push(-ZW + rnd() * 2 * ZW); wx.push((rnd() - 0.5) * (L + 0.6)); wh.push(0.1 + rnd() * 0.9); }
    const wg = new THREE.BufferGeometry(); wg.setAttribute('position', new THREE.BufferAttribute(wp, 3)); wg.setAttribute('color', new THREE.BufferAttribute(wc, 3));
    const vientoP = new THREE.Points(wg, new THREE.PointsMaterial({ size: 0.07, vertexColors: true, transparent: true, opacity: 0.95, depthWrite: false }));
    vientoP.frustumCulled = false; g.add(vientoP);
    // AIRE INTERIOR: entra por las rejillas bajas y sube a la garganta (velocidad = física)
    const NA = Math.round(L * 30), ag = new THREE.BufferGeometry(); ag.setAttribute('position', new THREE.BufferAttribute(new Float32Array(NA * 3), 3));
    const aire = new THREE.Points(ag, new THREE.PointsMaterial({ color: 0x2d9cff, size: 0.08, transparent: true, opacity: 0.9, depthWrite: false }));
    aire.frustumCulled = false; g.add(aire);
    const aph = Array.from({ length: NA }, (_, i) => [rnd(), (rnd() - 0.5) * (L - 0.4), i % 2 ? 1 : -1]);
    const bez = (a0, a1, a2, t) => (1 - t) * (1 - t) * a0 + 2 * (1 - t) * t * a1 + t * t * a2;
    let AT = 0, apert = 0;
    extrasUpd.push(dt => {
      const fz = est.fisica || {};
      const vWind = fz.viento ?? 3, vIn = fz.v_entrada ?? (est.claraboya > 0 ? 1 : 0.1), q = fz.caudal_m3h ?? (est.claraboya > 0 ? 3000 : 0);
      const dentro = [...avatares.values()].filter(a => Math.abs(a.grupo.position.x) < L / 2 - 0.15);
      apert += (est.claraboya - apert) * Math.min(1, dt * 2);
      for (const c of compuertas) c.piv.rotation.x = c.sz * apert * 1.2;       // compuertas abiertas = succión
      const fan = est.ventilador ? 1 : 0;
      for (const f of extract) f.rotation.y += dt * 14 * fan;
      for (const pu of puertas) {    // se abre si alguien está a menos de 1,4 m
        const cerca = [...avatares.values()].some(a => Math.abs(a.grupo.position.x - pu.x) < 1.4);
        pu.o += ((cerca ? 1 : 0) - pu.o) * Math.min(1, dt * 3); pu.m.position.z = Z + pu.o;
      }
      for (const c of camaras) { const act = dentro.some(a => Math.abs(a.grupo.position.x - c.x) < 1.6);
        c.led.material.color.set(act ? 0x2eff7a : 0xff3b30); c.fov.material.color.set(act ? 0x2eff7a : 0xffcc33); c.fov.material.opacity = act ? 0.14 : 0.07; }
      // aire interior: recorre el trayecto rejilla -> garganta a v_entrada (m/s); con la garganta cerrada no hay renovación
      aire.visible = q > 30;
      const recorrido = 2 * (HW + yc);                                 // longitud aproximada del trayecto (m)
      AT += dt * Math.max(0.02, vIn) / recorrido;
      const a = ag.attributes.position;
      for (let i = 0; i < NA; i++) { const qq = aph[i], t = (qq[0] + AT) % 1;
        a.setXYZ(i, qq[1] + Math.sin(t * 6 + i) * 0.05, bez(0.3, 1.4, yc + 0.3, t), bez(qq[2] * (HW + 0.5), qq[2] * 0.3 * HW, 0, t) + Z); }
      a.needsUpdate = true;
      const wpa = wg.attributes.position, wca = wg.attributes.color;
      for (let i = 0; i < NW; i++) {
        const zz0 = wz[i], rr = Math.hypot(zz0, wh[i] + Rr);              // distancia al eje del techo
        const ace = 1 + (K_CIMA - 1) * Math.exp(-zz0 * zz0 / (Rr * Rr)) * Math.pow(Rr / Math.max(Rr, rr), 2);
        wz[i] += dt * vWind * ace * 0.35; if (wz[i] > ZW) wz[i] = -ZW;      // 0,35: cámara lenta legible
        const zz = wz[i], ys = Math.abs(zz) < Rr ? Math.sqrt(Rr * Rr - zz * zz) : 0;
        wpa.setXYZ(i, wx[i], 2.75 + wh[i] + ys, zz + Z);
        const f = Math.min(1, (ace - 1) / (K_CIMA - 1)); wca.setXYZ(i, 0.25 + 0.75 * f, 0.65 + 0.15 * f, 1 - 0.7 * f); }
      wpa.needsUpdate = true; wca.needsUpdate = true;
    });
  }
  if (tipo === 'pergola') {
    // «Refugi climàtic» (diseño del equipo): plataforma de madera 6,4 x 4,4 m, toldo tensado 11,6 x 7,6 m
    // a 3,5 m, núcleo hexagonal con biblioteca, mesa y bancos con jardinera.
    const Z = -2.4, DK = 0.4;
    const rnd = aleatorio(12345);
    const cvs = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; };
    const cMad = cvs(256, 256), xm = cMad.getContext('2d');
    for (let i = 0; i < 8; i++) { const t = rnd();
      xm.fillStyle = `rgb(${214 + Math.round((t - 0.5) * 22)},${166 + Math.round((t - 0.5) * 22)},${104 + Math.round((t - 0.5) * 20)})`; xm.fillRect(0, i * 32, 256, 32);
      for (let k = 0; k < 14; k++) { xm.strokeStyle = `rgba(120,78,34,${0.05 + rnd() * 0.12})`; xm.lineWidth = 0.6 + rnd() * 1.1; const y = i * 32 + 2 + rnd() * 28;
        xm.beginPath(); xm.moveTo(0, y); xm.bezierCurveTo(80, y + (rnd() - 0.5) * 3, 170, y + (rnd() - 0.5) * 3, 256, y); xm.stroke(); }
      xm.fillStyle = 'rgba(90,56,22,.55)'; xm.fillRect(0, i * 32, 256, 1.4); }
    const tMad = new THREE.CanvasTexture(cMad); tMad.wrapS = tMad.wrapT = THREE.RepeatWrapping; tMad.colorSpace = THREE.SRGBColorSpace;
    const tMadV = tMad.clone(); tMadV.needsUpdate = true; tMadV.center.set(0.5, 0.5); tMadV.rotation = Math.PI / 2;
    const madera = new THREE.MeshStandardMaterial({ map: tMad, roughness: 0.82 }), maderaV = new THREE.MeshStandardMaterial({ map: tMadV, roughness: 0.82 });
    const maderaOsc = new THREE.MeshStandardMaterial({ color: 0xb08a58, map: tMad, roughness: 0.88 });
    const acero = new THREE.MeshStandardMaterial({ color: 0x4b5057, roughness: 0.5, metalness: 0.4 });
    const tierraM = new THREE.MeshStandardMaterial({ color: 0x3a2c20 });
    const escUV = (gm, w, h, d) => { const uv = gm.attributes.uv, dims = [[d, h], [d, h], [w, d], [w, d], [w, h], [w, h]];
      for (let f = 0; f < 6; f++) for (let i = 0; i < 4; i++) { const k = f * 4 + i; uv.setXY(k, uv.getX(k) * dims[f][0], uv.getY(k) * dims[f][1]); } uv.needsUpdate = true; };
    const mk = (w, h, d, mat, x, y, z) => { const gm = new THREE.BoxGeometry(w, h, d); escUV(gm, w, h, d);
      const m = new THREE.Mesh(gm, mat); m.position.set(x, y, z + Z); m.castShadow = m.receiveShadow = true; g.add(m); return m; };
    const viga = (a, b, w, h, mat) => { a = a.clone(); b = b.clone(); a.z += Z; b.z += Z; const L = a.distanceTo(b), gm = new THREE.BoxGeometry(w, h, L); escUV(gm, w, h, L);
      const m = new THREE.Mesh(gm, mat); m.position.copy(a).add(b).multiplyScalar(0.5); m.lookAt(b); m.castShadow = m.receiveShadow = true; g.add(m); return m; };
    const V3 = (x, y, z) => new THREE.Vector3(x, y, z);
    const verdes = [0x4a7a2c, 0x5a8a33, 0x3e6b28, 0x6a9a40, 0x7da644].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.9, flatShading: true }));
    const geoB = new THREE.IcosahedronGeometry(1, 1);
    const bola = (x, y, z, r) => { const m = new THREE.Mesh(geoB, verdes[(rnd() * 5) | 0]); m.position.set(x, y, z + Z); m.scale.setScalar(r);
      m.rotation.set(rnd() * 6, rnd() * 6, rnd() * 6); m.castShadow = true; g.add(m); };
    const arbusto = (cx, cy, cz, sx, sz, k, r0, r1, hm) => { for (let i = 0; i < k; i++) bola(cx + (rnd() - 0.5) * 2 * sx, cy + rnd() * hm, cz + (rnd() - 0.5) * 2 * sz, r0 + rnd() * (r1 - r0)); };
    // plataforma
    mk(6.3, 0.2, 4.3, maderaOsc, 0, 0.22, 0); mk(6.4, 0.1, 4.4, madera, 0, 0.35, 0);
    [[-3, -2], [3, -2], [-3, 2], [3, 2], [0, -2], [0, 2]].forEach(q => mk(0.34, 0.13, 0.34, maderaOsc, q[0], 0.065, q[1]));
    // pilares, vigas y radios del toldo
    const PX = 3.2, PZ = 2.2, PTOP = 2.9;
    [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(q => { mk(0.3, 0.08, 0.3, acero, q[0] * PX, DK + 0.04, q[1] * PZ);
      mk(0.24, PTOP - DK - 0.08, 0.24, maderaV, q[0] * PX, DK + 0.08 + (PTOP - DK - 0.08) / 2, q[1] * PZ); });
    [-1, 1].forEach(q => { viga(V3(-PX - 0.1, PTOP + 0.04, q * PZ), V3(PX + 0.1, PTOP + 0.04, q * PZ), 0.16, 0.22, madera);
      viga(V3(q * PX, PTOP + 0.04, -PZ - 0.1), V3(q * PX, PTOP + 0.04, PZ + 0.1), 0.16, 0.22, madera); });
    const CTR = V3(0, 3.44, 0);
    [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(q => { viga(CTR, V3(q[0] * 5.55, 2.5, q[1] * 3.65), 0.16, 0.2, madera);
      viga(V3(q[0] * PX, PTOP + 0.04, q[1] * PZ), V3(q[0] * 5.5, 2.72, q[1] * PZ), 0.14, 0.18, madera);
      viga(V3(q[0] * PX, PTOP + 0.04, q[1] * PZ), V3(q[0] * PX, 2.74, q[1] * 3.6), 0.14, 0.18, madera); });
    [[-1, 0], [1, 0], [0, -1], [0, 1]].forEach(q => viga(CTR, V3(q[0] * 5.3, 2.78, q[1] * 3.45), 0.13, 0.16, madera));
    const anillo2 = new THREE.Mesh(new THREE.CylinderGeometry(0.26, 0.3, 0.2, 10), maderaOsc); anillo2.position.set(0, 3.44, Z); g.add(anillo2);
    const fg = new THREE.PlaneGeometry(11.6, 7.6, 48, 32); fg.rotateX(-Math.PI / 2);
    { const pa = fg.attributes.position;
      for (let i = 0; i < pa.count; i++) { const x = pa.getX(i), z = pa.getZ(i), u = x / 5.8, v = z / 3.8, r2 = (u * u + v * v) / 2;
        pa.setY(i, 2.55 + 0.95 * Math.pow(Math.max(0, 1 - r2), 1.3));
        pa.setX(i, x * (1 - 0.08 * (1 - v * v) * Math.pow(Math.abs(u), 4))); pa.setZ(i, z * (1 - 0.08 * (1 - u * u) * Math.pow(Math.abs(v), 4)) + Z); }
      fg.computeVertexNormals(); }
    const toldo = new THREE.Mesh(fg, new THREE.MeshStandardMaterial({ color: 0xefe4cc, emissive: 0x3a3122, emissiveIntensity: 0.55, roughness: 0.92, side: THREE.DoubleSide }));
    toldo.castShadow = toldo.receiveShadow = true; g.add(toldo);
    // núcleo hexagonal con biblioteca
    const C = { x: 0, z: -0.9 }, A = 1.35, T = 0.12, HH = 2.3;
    for (let i = 1; i < 6; i++) { const phi = i * Math.PI / 3, d = A - T / 2; const w = mk(1.64, HH, T, madera, C.x + Math.sin(phi) * d, DK + HH / 2, C.z + Math.cos(phi) * d); w.rotation.y = phi; }
    const cartel = (lineas, tam, phi) => { const c = cvs(512, 1024), x = c.getContext('2d'); x.fillStyle = '#5a5148'; x.font = `600 ${tam}px system-ui,sans-serif`;
      lineas.forEach((l, i) => x.fillText(l, 60, 170 + i * tam * 1.15)); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
      const m = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 2.2), new THREE.MeshStandardMaterial({ map: t, transparent: true, roughness: 0.9, polygonOffset: true, polygonOffsetFactor: -2 }));
      const dd = A + 0.006; m.position.set(C.x + Math.sin(phi) * dd, DK + HH / 2, C.z + Math.cos(phi) * dd + Z); m.rotation.y = phi; g.add(m); };
    cartel(['Refugi', 'climàtic'], 92, 5 * Math.PI / 3); cartel(['Un espai', 'més fresc', 'per a tothom'], 62, Math.PI / 3);
    [-1, 1].forEach(q => { const hx = q * 0.78, hz = C.z + 1.35; mk(0.16, HH, 0.16, maderaV, hx, DK + HH / 2, hz);
      const pu = mk(0.05, HH - 0.1, 0.8, maderaV, hx + Math.sin(q * 0.44) * 0.42, DK + HH / 2, hz + Math.cos(0.44) * 0.42); pu.rotation.y = q * 0.44; });
    const shZ = C.z - (A - T) + 0.185;
    [-1, 1].forEach(q => mk(0.04, 2.1, 0.34, madera, q * 0.65, DK + 1.05, shZ));
    for (let i = 0; i < 5; i++) mk(1.34, 0.04, 0.34, madera, 0, DK + 0.05 + i * 0.5, shZ);
    const mLib = [0xd8c8a6, 0xcdb98e, 0xe0d2b2, 0x9a5b3e, 0x456a8a].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.9 }));
    for (let r = 0; r < 4; r++) for (let j = 0; j < 8; j++) { const bh = 0.3 + rnd() * 0.12; const b = new THREE.Mesh(new THREE.BoxGeometry(0.14, bh, 0.27), mLib[(rnd() * 5) | 0]);
      b.position.set(-0.57 + j * 0.163, DK + 0.07 + r * 0.5 + bh / 2, shZ + 0.02 + Z); b.castShadow = true; g.add(b); }
    for (let i = 0; i < 16; i++) { const aa = Math.PI * (0.55 + rnd() * 0.9); bola(C.x + Math.sin(aa + Math.PI) * (0.5 + rnd() * 0.9), DK + HH + 0.15 + rnd() * 0.35, C.z - Math.cos(aa + Math.PI) * (0.5 + rnd() * 0.9), 0.25 + rnd() * 0.25); }
    // mesa y bancos interiores
    mk(2.5, 0.05, 0.75, madera, 0.35, DK + 0.45, 0.3);
    [[-0.85, 0.05], [1.55, 0.05], [-0.85, 0.55], [1.55, 0.55]].forEach(q => mk(0.06, 0.43, 0.06, maderaOsc, q[0], DK + 0.215, q[1]));
    for (const bz of [-0.42, 1.0]) { mk(2.4, 0.05, 0.34, madera, 0.35, DK + 0.375, bz); [-0.8, 1.5].forEach(x => mk(0.06, 0.35, 0.3, maderaOsc, x, DK + 0.175, bz)); }
    mk(0.4, 0.4, 0.4, madera, 1.95, DK + 0.2, 0.35); mk(0.4, 0.4, 0.4, madera, 2.45, DK + 0.2, -0.2);
    // bancos con jardinera delante y jardineras detrás
    for (const cx of [-4.5, 4.5]) { mk(2.2, 0.85, 0.7, madera, cx, 0.425, 1.5); mk(2.0, 0.04, 0.5, tierraM, cx, 0.86, 1.5);
      arbusto(cx, 0.95, 1.5, 0.85, 0.14, 9, 0.34, 0.55, 0.55); mk(2.2, 0.08, 0.5, madera, cx, 0.46, 2.05);
      mk(0.08, 0.42, 0.4, maderaOsc, cx - 1.0, 0.21, 2.05); mk(0.08, 0.42, 0.4, maderaOsc, cx + 1.0, 0.21, 2.05);
      const re = mk(2.2, 0.5, 0.06, madera, cx, 0.78, 1.86); re.rotation.x = -0.18; }
    [-1, 1].forEach(q => { mk(1.3, 0.55, 0.8, madera, q * 2.5, DK + 0.275, -1.6); mk(1.15, 0.04, 0.65, tierraM, q * 2.5, DK + 0.57, -1.6);
      arbusto(q * 2.5, DK + 0.7, -1.6, 0.55, 0.3, 9, 0.3, 0.5, 0.8); });
    // nebulizadores bajo el toldo
    for (let k = 0; k < 6; k++) toberasNeb.push({ x: -2.5 + k, z: Z + 0.6, y: 2.75 });
  }
  if (esCupula) fuente(limites.minX - 0.9, -1.6); else if (tipo === 'pergola') fuente(-6.2, -1.0); else if (tipo === 'pabellon') fuente(-LP / 2 - 1.6, 0.6 + ZP + 1.4); else if (tipo === 'marquesina') fuente(-3.9, -0.4); else fuente(2.7, -0.8);

  // --- luz interior (noche) ---
  const luzInt = new THREE.PointLight(0xffc27a, 0, 8); luzInt.position.set(0, TOPE - 0.4, (limites.minZ + limites.maxZ) / 2);
  g.add(luzInt);

  // --- partículas ---
  const chorroAC = crearChorro(50 * n, { color: 0x4aa8ff, size: 0.12, opacity: 0.8, vida: 2.2, emitir(p, v, i) {
    const t = toberasAC[Math.floor(Math.random() * toberasAC.length)];
    if (!t) return false;   // tipos sin cúpula: el AC no tiene rejillas interiores
    p[i] = t.x; p[i + 1] = 2.1 + Math.random() * 0.2; p[i + 2] = t.z + (Math.random() - 0.5) * 1.2;
    v[i] = t.dir * (0.4 + Math.random() * 0.3); v[i + 1] = -0.15 - Math.random() * 0.15; v[i + 2] = (Math.random() - 0.5) * 0.1; } });
  const chorroNeb = crearChorro(70 * n, { color: 0xffffff, size: 0.3, opacity: 0.35, vida: 3, emitir(p, v, i) {
    const t = toberasNeb[Math.floor(Math.random() * toberasNeb.length)];
    if (!t) return false;
    p[i] = t.x + (Math.random() - 0.5) * 0.8; p[i + 1] = t.y ?? TOPE - 0.25; p[i + 2] = t.z + (Math.random() - 0.5) * 1.6;
    v[i] = (Math.random() - 0.5) * 0.15; v[i + 1] = -0.25 - Math.random() * 0.15; v[i + 2] = (Math.random() - 0.5) * 0.15; } });
  g.add(chorroAC.pts, chorroNeb.pts);

  // --- personas ---
  const sueloY = tipo === 'pergola' ? 0.4 : 0;   // personas sobre la plataforma de madera
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
    const alto = 1.55 + r() * 0.15, k = alto / 1.75;
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
    a.rig = nuevoRig(personaBase, 0.82);   // modelo 1,83 m -> ~1,50-1,65 m con la escala del dorso
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
        a.objetivo.set(clampX(p.x), sueloY, clampZ(-p.y));
        a.estado = p.estado || 'de_pie';
        if (a.nuevo) { a.grupo.position.copy(a.objetivo); a.nuevo = false; }
      });
      for (const [k, a] of avatares) if (!vistos.has(k)) {
        g.remove(a.grupo); a.grupo.traverse(o => { if (o.userData.compartido) { o.material?.dispose?.(); return; }
          o.geometry?.dispose(); o.material?.map?.dispose(); o.material?.dispose?.(); });
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
      g.traverse(o => { if (o.userData.compartido) return; o.geometry?.dispose();
        const ms = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
        ms.forEach(m => { m.map?.dispose(); m.dispose(); }); });
    },
  };
  g.traverse(o => { if (o.isMesh && o.material !== mVidrio && o.material !== mAire) { o.castShadow = true; o.receiveShadow = true; } });
  scene.add(g);
  return api;
}
