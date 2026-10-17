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

export const LADO = 3;          // m, lado del módulo
const BASE = 1.2;               // altura de los pilares / arranque de la bóveda
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
function crearChorro(n, { color, size, opacity, emitir, vida }) {
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
        pos[i * 3] += vel[i * 3] * dt; pos[i * 3 + 1] += vel[i * 3 + 1] * dt; pos[i * 3 + 2] += vel[i * 3 + 2] * dt;
        if (pos[i * 3 + 1] < 0.1) life[i] = 0;
      }
      geo.attributes.position.needsUpdate = true;
    },
  };
}

function aleatorio(semilla) { let s = semilla; return () => (s = (s * 16807) % 2147483647) / 2147483647; }

export function construirRefugio(scene, { kit = 'parada_bus', n = 2 } = {}) {
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
  const limites = { minX: -cols * R, maxX: cols * R, minZ: -filas * LADO, maxZ: 0 };

  // --- materiales ---
  const mVidrio = new THREE.MeshPhysicalMaterial({ color: 0xcfeee0, transmission: 0.9, roughness: 0.05,
    thickness: 0.08, ior: 1.45, transparent: true, side: THREE.DoubleSide, attenuationColor: new THREE.Color(0x9fe0c0),
    attenuationDistance: 3 });
  const mEstruct = new THREE.MeshStandardMaterial({ color: 0x3c4a44, metalness: 0.7, roughness: 0.4 });
  const mSuelo = new THREE.MeshStandardMaterial({ color: 0x8a6a4a, roughness: 0.85 });
  const mBanco = new THREE.MeshStandardMaterial({ color: 0xb98a55, roughness: 0.7 });
  const mTierra = new THREE.MeshStandardMaterial({ color: 0x4a3322, roughness: 1 });
  const mMacetero = new THREE.MeshStandardMaterial({ color: 0x7a7a72, roughness: 0.8 });
  const mVerde = [0x2f9a4a, 0x3fb858, 0x23803c].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.8 }));
  const mAire = new THREE.MeshBasicMaterial({ color: 0x9fd8c0, transparent: true, opacity: 0.12, depthWrite: false });
  const mFV = [];   // un material por tira (textura con su repetición)
  const mClar = new THREE.MeshPhysicalMaterial({ color: 0xcfeee0, transmission: 0.85, roughness: 0.05, transparent: true,
    side: THREE.DoubleSide });

  // --- suelo ---
  for (let c = 0; c < cols; c++) {
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
  const toberasAC = [], toberasNeb = [];
  modulos.forEach((m, i) => {
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
  ac.position.set(limites.maxX + 0.45, 0, m0.cz); g.add(ac);

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
  if (kit === 'parada_bus') {
    const poste = new THREE.Group();
    const tubo = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 2.9, 10), mEstruct); tubo.position.y = 1.45;
    const cv = document.createElement('canvas'); cv.width = cv.height = 128;
    const cg = cv.getContext('2d'); cg.fillStyle = '#d4202a'; cg.fillRect(0, 0, 128, 128);
    cg.fillStyle = '#fff'; cg.font = 'bold 56px system-ui'; cg.textAlign = 'center'; cg.textBaseline = 'middle'; cg.fillText('BUS', 64, 64);
    const letrero = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.45, 0.04), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(cv) }));
    letrero.position.set(0, 2.65, 0);
    const techo = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.05, 0.9), mEstruct); techo.position.set(-0.7, 2.5, -0.1);
    poste.add(tubo, letrero, techo);
    poste.position.set(limites.maxX + 0.6, 0, 0.8); g.add(poste);
  }

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
    p[i] = t.x + (Math.random() - 0.5) * 0.8; p[i + 1] = TOPE - 0.25; p[i + 2] = t.z + (Math.random() - 0.5) * 1.6;
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
    const mat = new THREE.MeshStandardMaterial({ color: mats.normal, roughness: 0.6, emissive: 0x000000 });
    const cuerpo = new THREE.Mesh(new THREE.CapsuleGeometry(0.17, 0.8, 4, 12), mat); cuerpo.position.y = 0.6;
    const cabeza = new THREE.Mesh(new THREE.SphereGeometry(0.13, 16, 12), new THREE.MeshStandardMaterial({ color: 0xf0c8a0, roughness: 0.7 }));
    cabeza.position.y = 1.32;
    const dorso = new THREE.Group(); dorso.add(cuerpo, cabeza);
    grupo.add(dorso);
    const etiqueta = crearEtiqueta(`Persona ${p.id ?? idx + 1}`); etiqueta.position.set(0, 1.9, 0);
    grupo.add(etiqueta);
    g.add(grupo);
    return { grupo, dorso, mat, etiqueta, objetivo: new THREE.Vector3(), rotX: 0, escY: 1, nuevo: true, id: p.id };
  }
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
      // personas
      let objetivoDesm = null;
      if (desmayo.activo) {
        objetivoDesm = avatares.get(desmayo.persona) ?? [...avatares.values()].find(a => a.estado === 'suelo') ?? avatares.values().next().value ?? null;
      }
      for (const a of avatares.values()) {
        a.grupo.position.lerp(a.objetivo, k);
        const suelo = a.estado === 'suelo', sentado = a.estado === 'sentado';
        a.rotX += ((suelo ? -Math.PI / 2 : 0) - a.rotX) * k;
        a.escY += ((sentado ? 0.65 : 1) - a.escY) * k;
        a.dorso.rotation.x = a.rotX;
        a.dorso.scale.y = a.escY;
        a.dorso.position.y = suelo ? 0.2 : sentado ? 0.15 : 0;
        a.etiqueta.position.y = suelo ? 0.8 : sentado ? 1.4 : 1.9;
        const rojo = a === objetivoDesm;
        a.mat.color.set(rojo ? mats.rojo : mats.normal);
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
      scene.remove(g);
      g.traverse(o => { o.geometry?.dispose();
        const ms = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
        ms.forEach(m => { m.map?.dispose(); m.dispose(); }); });
    },
  };
  scene.add(g);
  return api;
}
