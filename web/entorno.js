// Entorno alrededor del refugio: 'bus' (acera + calzada + carril bus), 'plaza' (pavimento,
// árboles, farolas, bancos) o 'terraza' (azotea de edificio con barandilla y la ciudad abajo).
// construirEntorno(scene, lugar) -> { dispose() }. El refugio queda en el origen (frente en z = 0).
import * as THREE from 'three';

function tex(pintar, rep, size = 128) {
  const c = document.createElement('canvas'); c.width = c.height = size; pintar(c.getContext('2d'), size);
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(rep, rep);
  t.colorSpace = THREE.SRGBColorSpace; return t;
}
const baldosa = (fondo, linea, paso) => (x, n) => {
  x.fillStyle = fondo; x.fillRect(0, 0, n, n); x.strokeStyle = linea; x.lineWidth = 2;
  for (let i = 0; i <= n; i += paso) { x.beginPath(); x.moveTo(i, 0); x.lineTo(i, n); x.stroke(); x.beginPath(); x.moveTo(0, i); x.lineTo(n, i); x.stroke(); }
};
const grava = (x, n) => {
  x.fillStyle = '#9b978f'; x.fillRect(0, 0, n, n);
  for (let i = 0; i < 900; i++) { const v = 120 + Math.random() * 70 | 0; x.fillStyle = `rgb(${v},${v - 4},${v - 10})`; x.fillRect(Math.random() * n, Math.random() * n, 2, 2); }
};

function caja(g, w, h, d, color, x, y, z, extra = {}) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), new THREE.MeshStandardMaterial({ color, roughness: 0.85, ...extra }));
  m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; g.add(m); return m;
}
function arbol(g, x, z, alto = 4) {
  const tr = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.22, alto * 0.55, 10), new THREE.MeshStandardMaterial({ color: 0x6b4a2f, roughness: 0.9 }));
  tr.position.set(x, alto * 0.275, z); tr.castShadow = true; g.add(tr);
  const mh = new THREE.MeshStandardMaterial({ color: 0x3f8f4a, roughness: 0.9 });
  for (const [dx, dy, r] of [[0, 0.75, 1.1], [0.55, 0.55, 0.8], [-0.5, 0.6, 0.85], [0.1, 1.05, 0.75]]) {
    const s = new THREE.Mesh(new THREE.IcosahedronGeometry(r, 1), mh); s.position.set(x + dx, alto * dy + 0.6, z + dx * 0.4); s.castShadow = true; g.add(s);
  }
}
function farola(g, x, z) {
  const m = new THREE.MeshStandardMaterial({ color: 0x2b3436, metalness: 0.6, roughness: 0.4 });
  const p = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.07, 4, 10), m); p.position.set(x, 2, z); p.castShadow = true; g.add(p);
  const b = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.05, 0.05), m); b.position.set(x + 0.3, 3.95, z); g.add(b);
  const l = new THREE.Mesh(new THREE.SphereGeometry(0.14, 12, 8), new THREE.MeshStandardMaterial({ color: 0xfff1c9, emissive: 0xffd88a, emissiveIntensity: 0.6 }));
  l.position.set(x + 0.62, 3.85, z); g.add(l);
}
function banco(g, x, z, rot = 0) {
  const b = new THREE.Group(); b.position.set(x, 0, z); b.rotation.y = rot; g.add(b);
  const mm = new THREE.MeshStandardMaterial({ color: 0x9a6b3f, roughness: 0.7 }), mf = new THREE.MeshStandardMaterial({ color: 0x2b3436, metalness: 0.6 });
  const s = new THREE.Mesh(new THREE.BoxGeometry(1.8, 0.06, 0.42), mm); s.position.y = 0.48; b.add(s);
  const r = new THREE.Mesh(new THREE.BoxGeometry(1.8, 0.38, 0.05), mm); r.position.set(0, 0.75, -0.19); b.add(r);
  for (const sx of [-0.75, 0.75]) { const p = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.48, 0.38), mf); p.position.set(sx, 0.24, 0); b.add(p); }
  b.traverse(o => { if (o.isMesh) o.castShadow = true; });
}

export function construirEntorno(scene, lugar = 'bus') {
  const g = new THREE.Group(); g.name = 'entorno';
  const fondo = { bus: 0x9ec9e6, plaza: 0xa9d3ea, terraza: 0x8fc0e6 }[lugar] ?? 0x9ec9e6;
  scene.background = new THREE.Color(fondo);
  scene.fog = new THREE.Fog(fondo, lugar === 'terraza' ? 40 : 25, lugar === 'terraza' ? 140 : 70);

  if (lugar === 'bus') {
    const suelo = new THREE.Mesh(new THREE.PlaneGeometry(120, 120), new THREE.MeshStandardMaterial({ map: tex(baldosa('#b9b5ac', '#9d988e', 32), 30), roughness: 0.95 }));
    suelo.rotation.x = -Math.PI / 2; suelo.position.y = -0.11; suelo.receiveShadow = true; g.add(suelo);
    const calzada = new THREE.Mesh(new THREE.PlaneGeometry(120, 7), new THREE.MeshStandardMaterial({ color: 0x3a3d40, roughness: 0.9 }));
    calzada.rotation.x = -Math.PI / 2; calzada.position.set(0, -0.1, 6.5); calzada.receiveShadow = true; g.add(calzada);
    caja(g, 120, 0.15, 0.25, 0xd8d4cc, 0, -0.04, 2.9);
    const carril = new THREE.Mesh(new THREE.PlaneGeometry(120, 3), new THREE.MeshStandardMaterial({ color: 0xa8382f, roughness: 0.9 }));
    carril.rotation.x = -Math.PI / 2; carril.position.set(0, -0.095, 4.6); g.add(carril);
    const rc = document.createElement('canvas'); rc.width = 256; rc.height = 64;
    { const x = rc.getContext('2d'); x.fillStyle = '#fff'; x.font = 'bold 54px system-ui'; x.textAlign = 'center'; x.fillText('BUS', 128, 52); }
    const rot = new THREE.Mesh(new THREE.PlaneGeometry(2.4, 0.6), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(rc), transparent: true }));
    rot.rotation.x = -Math.PI / 2; rot.position.set(0, -0.09, 4.6); g.add(rot);
    for (let i = -1; i <= 1; i += 2) for (let k = 0; k < 6; k++) caja(g, 1.6, 0.012, 0.12, 0xf2f2f2, -18 + k * 7 * i, -0.09, 8.1);   // línea discontinua
    for (const x of [-12, 12]) { arbol(g, x, 1.6, 4.5); farola(g, x + 4, 2.4); }
    // fachadas al fondo
    for (let k = -4; k <= 4; k++) caja(g, 7.6, 9 + ((k * 37 + 70) % 6), 6, [0xd8c7a8, 0xc9b79a, 0xe0d4bd][(k + 9) % 3], k * 8, 4.5, -24);
  }

  if (lugar === 'plaza') {
    const suelo = new THREE.Mesh(new THREE.PlaneGeometry(120, 120), new THREE.MeshStandardMaterial({ map: tex(baldosa('#d8cdb6', '#bfb39a', 64), 24), roughness: 0.95 }));
    suelo.rotation.x = -Math.PI / 2; suelo.position.y = -0.11; suelo.receiveShadow = true; g.add(suelo);
    const cesped = new THREE.MeshStandardMaterial({ color: 0x5f9a4a, roughness: 1 });
    for (const [x, z] of [[-11, -2], [11, -2], [-11, 7], [11, 7]]) {
      const c = new THREE.Mesh(new THREE.CylinderGeometry(3.2, 3.2, 0.2, 32), cesped); c.position.set(x, -0.02, z); c.receiveShadow = true; g.add(c);
      arbol(g, x, z, 5);
      caja(g, 6.6, 0.35, 0.2, 0xb8ad96, x, 0.06, z + 3.3);
    }
    for (const [x, z] of [[-6, 6], [6, 6], [-6, -9], [6, -9]]) farola(g, x, z);
    banco(g, -3.5, 6.5, Math.PI); banco(g, 3.5, 6.5, Math.PI); banco(g, 0, -10, 0);
    // fuente ornamental central delante
    const pila = new THREE.Mesh(new THREE.CylinderGeometry(1.6, 1.7, 0.5, 32), new THREE.MeshStandardMaterial({ color: 0xc8bfae, roughness: 0.8 }));
    pila.position.set(0, 0.15, 11); pila.castShadow = true; g.add(pila);
    const agua = new THREE.Mesh(new THREE.CircleGeometry(1.45, 32), new THREE.MeshStandardMaterial({ color: 0x4aa3d8, roughness: 0.1, metalness: 0.3 }));
    agua.rotation.x = -Math.PI / 2; agua.position.set(0, 0.41, 11); g.add(agua);
    for (let k = -4; k <= 4; k++) caja(g, 9.6, 10 + ((k * 53 + 90) % 7), 8, [0xe7d9bd, 0xd9c49e, 0xefe2c8][(k + 9) % 3], k * 10, 5, -38);
  }

  if (lugar === 'terraza') {
    // azotea de 18 x 16 m a cota 0 con pretil y barandilla; la ciudad 22 m más abajo
    const losa = new THREE.Mesh(new THREE.BoxGeometry(18, 0.4, 16), new THREE.MeshStandardMaterial({ map: tex(grava, 6), roughness: 1 }));
    losa.position.set(0, -0.31, -1); losa.receiveShadow = true; g.add(losa);
    const fach = new THREE.Mesh(new THREE.BoxGeometry(18, 22, 16), new THREE.MeshStandardMaterial({ color: 0xd9cdb5, roughness: 0.9 }));
    fach.position.set(0, -11.5, -1); g.add(fach);
    const mPret = 0xcfc6b4;
    caja(g, 18, 0.9, 0.25, mPret, 0, 0.35, 7); caja(g, 18, 0.9, 0.25, mPret, 0, 0.35, -9);
    caja(g, 0.25, 0.9, 16, mPret, 9, 0.35, -1); caja(g, 0.25, 0.9, 16, mPret, -9, 0.35, -1);
    const mBar = { color: 0x2b3436, metalness: 0.7, roughness: 0.3 };
    caja(g, 18, 0.05, 0.05, 0x2b3436, 0, 1.1, 7, mBar); caja(g, 0.05, 0.05, 16, 0x2b3436, 9, 1.1, -1, mBar); caja(g, 0.05, 0.05, 16, 0x2b3436, -9, 1.1, -1, mBar);
    // elementos de azotea: depósito, salida de escalera, chimeneas, máquinas
    const dep = new THREE.Mesh(new THREE.CylinderGeometry(0.8, 0.8, 1.6, 20), new THREE.MeshStandardMaterial({ color: 0xe8e8e2, roughness: 0.6 }));
    dep.position.set(-6.5, 0.7, -7); dep.castShadow = true; g.add(dep);
    caja(g, 2.6, 2.6, 2.4, 0xcfc6b4, 6.6, 1.2, -7.4);
    for (const x of [-3, -1.8]) caja(g, 0.4, 1.4, 0.4, 0xa9583f, x, 0.6, -8.4);
    for (const x of [2.5, 3.6]) caja(g, 0.9, 0.7, 0.5, 0xdfe5e2, x, 0.25, 5.8);
    for (const [x, z] of [[-7.5, 5.5], [7.5, 5.5]]) {
      const mac = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.4, 0.5, 16), new THREE.MeshStandardMaterial({ color: 0x8a6a4a })); mac.position.set(x, 0.15, z); g.add(mac);
      arbol(g, x, z, 2.2);
    }
    // ciudad abajo: suelo y manzanas
    const ciudad = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), new THREE.MeshStandardMaterial({ color: 0x8c8a84, roughness: 1 }));
    ciudad.rotation.x = -Math.PI / 2; ciudad.position.y = -22.5; g.add(ciudad);
    let s = 11; const r = () => (s = (s * 16807) % 2147483647) / 2147483647;
    const cols = [0xd8c7a8, 0xc9b79a, 0xe0d4bd, 0xb9a98e, 0xd2c2a4];
    for (let i = -6; i <= 6; i++) for (let k = -6; k <= 6; k++) {
      if (Math.abs(i) <= 1 && Math.abs(k) <= 1) continue;
      const h = 6 + r() * 13;               // azoteas vecinas por debajo de la nuestra
      const b = new THREE.Mesh(new THREE.BoxGeometry(16, h, 16), new THREE.MeshStandardMaterial({ color: cols[(i * 7 + k * 3 + 50) % 5], roughness: 0.9 }));
      b.position.set(i * 22, -22.5 + h / 2, k * 22 - 1); g.add(b);
    }
  }
  g.traverse(o => { if (o.isMesh && o.receiveShadow === false) o.receiveShadow = true; });
  scene.add(g);
  return {
    dispose() {
      scene.remove(g);
      g.traverse(o => { o.geometry?.dispose(); if (o.material) { o.material.map?.dispose(); o.material.dispose(); } });
    },
  };
}

export const LUGAR_POR_KIT = { parada_bus: 'bus', terraza_comunitaria: 'plaza', terraza_privada: 'terraza' };

// Posición del sol en Barcelona (41,39° N, 2,17° E) para una hora local de verano (CEST) y un día del año.
// Devuelve elevación y azimut (grados, azimut desde el norte hacia el este), la dirección hacia el sol en el
// marco three (norte = -z, este = +x) y la irradiancia directa de cielo despejado aproximada (W/m²).
export function posicionSol(hora, diaAnio = 200) {
  const rad = Math.PI / 180, lat = 41.39 * rad;
  const decl = 23.45 * rad * Math.sin(2 * Math.PI * (284 + diaAnio) / 365);
  const horaSolar = hora - 2 + 2.17 / 15;                 // CEST = UTC+2; longitud 2,17° E
  const H = (horaSolar - 12) * 15 * rad;
  const sinE = Math.sin(lat) * Math.sin(decl) + Math.cos(lat) * Math.cos(decl) * Math.cos(H);
  const elev = Math.asin(Math.max(-1, Math.min(1, sinE)));
  let az = Math.acos(Math.max(-1, Math.min(1, (Math.sin(decl) - Math.sin(elev) * Math.sin(lat)) / (Math.cos(elev) * Math.cos(lat)))));
  if (H > 0) az = 2 * Math.PI - az;                        // tarde: hacia el oeste
  const dir = new THREE.Vector3(Math.cos(elev) * Math.sin(az), Math.sin(elev), -Math.cos(elev) * Math.cos(az));
  const irr = elev > 0 ? Math.round(1000 * Math.pow(Math.sin(elev), 1.15)) : 0;
  return { elev: elev / rad, az: az / rad, dir, irr };
}
