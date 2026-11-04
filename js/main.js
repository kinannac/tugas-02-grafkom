const canvas = document.getElementById('glcanvas');
const gl = canvas.getContext('webgl', { antialias: true });
const status = document.getElementById('status');
if (!gl) status.textContent = 'WebGL tidak tersedia di browser ini.';

const VS = `
attribute vec3 aPos; attribute vec3 aNrm; attribute vec2 aUV;
uniform mat4 uModel, uView, uProj; uniform mat3 uNormalMat;
varying vec3 vN; varying vec2 vUV; varying vec3 vPos;
void main(){
  vec4 w = uModel * vec4(aPos,1.0);
  vPos = w.xyz; vN = uNormalMat * aNrm; vUV = aUV;
  gl_Position = uProj * uView * w;
}`;

const FS = `
precision mediump float;
varying vec3 vN; varying vec2 vUV; varying vec3 vPos;
uniform sampler2D uTex; uniform vec4 uColor; uniform float uSpec;
uniform vec3 uEye, uLightDir, uLightColor, uSky, uGround, uFogColor; uniform float uAmbient, uFog;
void main(){
  vec3 N = normalize(vN);
  if(!gl_FrontFacing) N = -N;
  vec3 base = texture2D(uTex, vUV).rgb * uColor.rgb;
  float ndl = max(dot(N, uLightDir), 0.0);
  vec3 hemi = mix(uGround, uSky, N.y*0.5+0.5) * uAmbient;               
  vec3 V = normalize(uEye - vPos), H = normalize(uLightDir + V);
  float spec = pow(max(dot(N,H),0.0), 40.0) * uSpec * step(0.0, ndl);  
  vec3 col = base * (hemi + uLightColor * ndl) + uLightColor * spec;    
  float d = length(uEye - vPos);
  col = mix(col, uFogColor, 1.0 - exp(-d*d*uFog*uFog));                
  gl_FragColor = vec4(col, 1.0);
}`;

function program(vs, fs) {
  const mk = (t, s) => { const o = gl.createShader(t); gl.shaderSource(o, s); gl.compileShader(o);
    if (!gl.getShaderParameter(o, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(o)); return o; };
  const p = gl.createProgram();
  gl.attachShader(p, mk(gl.VERTEX_SHADER, vs)); gl.attachShader(p, mk(gl.FRAGMENT_SHADER, fs));
  gl.bindAttribLocation(p, 0, 'aPos'); gl.bindAttribLocation(p, 1, 'aNrm'); gl.bindAttribLocation(p, 2, 'aUV');
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
  return p;
}

const prog = program(VS, FS);
const U = {};
['uModel', 'uView', 'uProj', 'uNormalMat', 'uTex', 'uColor', 'uSpec', 'uEye', 'uLightDir', 'uLightColor', 'uSky', 'uGround', 'uFogColor', 'uAmbient', 'uFog']
  .forEach(n => U[n] = gl.getUniformLocation(prog, n));
const whiteTex = (() => { const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([255, 255, 255, 255]));
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST); return t; })();

const PLACEMENT = [
  { id: 'Sign',   file: 'models/infinits_sign.glb', pos: [0, 0, 0] },
  { id: 'Ground', file: 'models/ground.glb',        pos: [0, 0, 0] },
  { id: 'Tree_1', file: 'models/tree.glb', pos: [-12, 0, -16],  yaw: 40,  scale: 0.85 },
  { id: 'Tree_2', file: 'models/tree.glb', pos: [-4, 0, -24],   yaw: 140, scale: 1.0 },
  { id: 'Tree_3', file: 'models/tree.glb', pos: [7, 0, -17],    yaw: 80,  scale: 0.85 },
  { id: 'Tree_4', file: 'models/tree.glb', pos: [14, 0, -14],   yaw: 200, scale: 0.8 },
  { id: 'Tree_5', file: 'models/tree.glb', pos: [-20, 0, -12],  yaw: 300, scale: 0.9 },
  { id: 'Tree_6', file: 'models/tree.glb', pos: [21, 0, -22],   yaw: 40,  scale: 1.0 },
  { id: 'Cat',    file: 'models/cat.glb',   pos: [0, 0, 3.0],   yaw: 90, scale: 1 },
  { id: 'Human',  file: 'models/human.glb', pos: [0, 0, 5.6],   yaw: -90, scale: 1 },
];

const objects = [];     //
const O = id => objects.find(o => o.id === id);
const tmp = new Float32Array(16), place = new Float32Array(16);

function updateWorld(n, parent) {
  M4.fromTRS(n.t, n.q, n.s, n.local);
  M4.mul(parent, n.local, n.world);
  for (const c of n.children) updateWorld(c, n.world);
}
function placementMatrix(o) {
  return M4.fromTRS(o.pos, Q.ry(o.yaw), [o.scale, o.scale, o.scale], place);
}

// animasi
const rad = d => d * Math.PI / 180;
function setRot(inst, name, q) { inst.node[name].q = q; }

function animateHuman(o, ph, moving) {
  const A = moving ? 1 : 0, s = Math.sin(ph), c = Math.cos(ph);
  const legs = [['L', 0], ['R', Math.PI]];

  for (const [side, off] of legs) {
    const sp = Math.sin(ph + off), cp = Math.cos(ph + off), sgn = side === 'L' ? 1 : -1;
    setRot(o.inst, `Human_Hip_${side}`, Q.rx(-30 * sp * A));                       
    setRot(o.inst, `Human_Knee_${side}`, Q.rx((6 + 42 * Math.max(0, cp)) * A));    
    setRot(o.inst, `Human_Ankle_${side}`, Q.rx(-8 * sp * A));
    setRot(o.inst, `Human_Shoulder_${side}`, Q.rx(26 * sp * A));                  
    setRot(o.inst, `Human_Elbow_${side}`, Q.rx(-(18 + 10 * (1 - sp)) * A));      
  }

  const pel = o.inst.node.Human_Pelvis;
  pel.t[1] = 0.93 + 0.018 * Math.cos(2 * ph) * A;                         
  pel.q = Q.ry(4 * s * A);
  setRot(o.inst, 'Human_Torso', Q.mul(Q.ry(-7 * s * A), Q.rx(3 * A)));
}

function animateCat(o, ph, t, moving) {
  const A = moving ? 1 : 0;
  const pairs = { FL: 0, BR: 0, FR: Math.PI, BL: Math.PI };
  for (const k in pairs) {
    const sp = Math.sin(ph + pairs[k]), cp = Math.cos(ph + pairs[k]);
    setRot(o.inst, `Cat_Leg_${k}_Upper`, Q.rx(-26 * sp * A));
    setRot(o.inst, `Cat_Leg_${k}_Lower`, Q.rx((6 + 30 * Math.max(0, cp)) * A));
  }
  o.inst.node.Cat_Body.t[1] = 0.29 + 0.006 * Math.cos(2 * ph) * A;
  setRot(o.inst, 'Cat_Head', Q.mul(Q.ry(6 * Math.sin(ph * 0.5)), Q.rx(4 * Math.sin(2 * ph) * A)));
  
  // ekor
  const sway = (k, base, amp, lag) => setRot(o.inst, `Cat_Tail${k}`, Q.mul(Q.ry(amp * Math.sin(t * 2.4 - lag)), Q.rx(base)));
  sway(1, 34, 14, 0); sway(2, 14, 18, 0.9); sway(3, 10, 22, 1.8);
  
  // telinga berkedut
  const tw = Math.pow(Math.max(0, Math.sin(t * 1.3)), 12) * 12;
  setRot(o.inst, 'Cat_Ear_L', Q.mul(Q.rz(-14 - tw), Q.rx(0)));
  setRot(o.inst, 'Cat_Ear_R', Q.rz(14));
  const blink = (t % 4) > 3.88 ? 0.1 : 1;
  for (const s of ['L', 'R']) o.inst.node[`Cat_Eye_${s}`].s = [1, blink, 1];
}

// Jalan bolak-balik 
function walker(o, cfg, t) {
  const L = cfg.x1 - cfg.x0, tMove = L / cfg.speed, tTurn = 1.0, cycle = 2 * (tMove + tTurn);
  const u = (t + cfg.phase) % cycle;
  let x, yaw, moving = true;
  if (u < tMove)                   { x = cfg.x0 + cfg.speed * u; yaw = 90; }
  else if (u < tMove + tTurn)      { x = cfg.x1; yaw = 90 + 180 * smooth((u - tMove) / tTurn); moving = false; }
  else if (u < 2 * tMove + tTurn)  { x = cfg.x1 - cfg.speed * (u - tMove - tTurn); yaw = 270; }
  else                             { x = cfg.x0; yaw = 270 + 180 * smooth((u - 2 * tMove - tTurn) / tTurn); moving = false; }
  o.pos = [x, 0, cfg.z]; 
  o.yaw = yaw;
  return moving;
}
const smooth = x => x * x * (3 - 2 * x);

// kamera 
const cam = { target: [0.3, 1.5, 0], yaw: 0, pitch: 0.02, dist: 13, fov: 40 };
let follow = null;

const PRESETS = {
  foto:    () => { follow = null; Object.assign(cam, { target: [0.3, 1.5, 0], yaw: 0, pitch: 0.02, dist: 13 }); },
  atas:    () => { follow = null; Object.assign(cam, { target: [0, 1, 2], yaw: 0.65, pitch: 0.55, dist: 26 }); },
  kucing:  () => { follow = 'Cat'; Object.assign(cam, { yaw: 0.9, pitch: 0.18, dist: 1.8 }); },
  manusia: () => { follow = 'Human'; Object.assign(cam, { yaw: 0.9, pitch: 0.12, dist: 4.5 }); },
};

// document.querySelectorAll('[data-cam]').forEach(b => b.addEventListener('click', () => PRESETS[b.dataset.cam]()));
let drag = null;

canvas.addEventListener('pointerdown', e => { drag = { x: e.clientX, y: e.clientY }; canvas.setPointerCapture(e.pointerId); });
canvas.addEventListener('pointerup', () => drag = null);
canvas.addEventListener('pointermove', e => {
  if (!drag) return;
  cam.yaw -= (e.clientX - drag.x) * 0.006; cam.pitch = Math.max(-0.05, Math.min(1.4, cam.pitch + (e.clientY - drag.y) * 0.006));
  drag = { x: e.clientX, y: e.clientY };
});
canvas.addEventListener('wheel', e => { e.preventDefault(); cam.dist = Math.max(1.2, Math.min(60, cam.dist * Math.exp(e.deltaY * 0.001))); }, { passive: false });

const ui = { animate: document.getElementById('chkAnim'), sun: document.getElementById('rngSun') };
let simT = 0, last = performance.now();

function draw(node, uModelOnly) {
  if (node.prims.length) {
    gl.uniformMatrix4fv(U.uModel, false, node.world);
    gl.uniformMatrix3fv(U.uNormalMat, false, M4.normal3(node.world));
    for (const p of node.prims) {
      gl.bindBuffer(gl.ARRAY_BUFFER, p.pos); gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, p.nrm); gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, p.uv);  gl.vertexAttribPointer(2, 2, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, p.idx);
      gl.bindTexture(gl.TEXTURE_2D, p.mat.tex || whiteTex);
      gl.uniform4fv(U.uColor, p.mat.color); gl.uniform1f(U.uSpec, p.mat.spec);
      gl.drawElements(gl.TRIANGLES, p.count, gl.UNSIGNED_SHORT, 0);
    }
  }
  for (const c of node.children) draw(c);
}

function frame(now) {
  const dt = Math.min(0.05, (now - last) / 1000); last = now;
  if (ui.animate.checked) simT += dt;

  const human = O('Human'), cat = O('Cat');
  const hm = walker(human, { x0: -9, x1: 9, z: 4, speed: 1.0, phase: 1 }, simT);
  const cm = walker(cat, { x0: -3, x1: 2, z: 3, speed: 0.5, phase: 2 }, simT);

  animateHuman(human, simT * 5.8, hm);
  animateCat(cat, simT * 8.0, simT, cm);

  for (const o of objects) if (o.id.startsWith('Tree')) {      
    const k = o.id.charCodeAt(5);
    o.inst.node.Canopy.q = Q.mul(Q.rz(1.2 * Math.sin(simT * 0.8 + k)), Q.rx(1.0 * Math.sin(simT * 0.6 + k * 2)));
  }

  for (const o of objects) updateWorld(o.inst.root, placementMatrix(o));

  if (follow) { 
    const p = O(follow).pos; 
    for (let i = 0; i < 3; i++) 
      cam.target[i] += ((i === 1 ? (follow === 'Cat' ? 0.25 : 1.0) : p[i]) - cam.target[i]) * 0.12; }

  const cp = Math.cos(cam.pitch);
  const eye = [cam.target[0] + cam.dist * Math.sin(cam.yaw) * cp, cam.target[1] + cam.dist * Math.sin(cam.pitch), cam.target[2] + cam.dist * Math.cos(cam.yaw) * cp];

  const el = rad(+ui.sun.value), az = 0.6, k = Math.min(1, (+ui.sun.value - 8) / 40);
  const sunDir = [Math.sin(az) * Math.cos(el), Math.sin(el), Math.cos(az) * Math.cos(el)];
  const warm = [1.0, 0.62, 0.40], white = [1.0, 0.95, 0.86], inten = 0.35 + 0.55 * Math.sqrt(Math.sin(el));
  const sunCol = warm.map((w, i) => (w + (white[i] - w) * k) * inten);
  const skyA = [0.80, 0.84, 0.88], skyB = [0.93, 0.62, 0.45];
  const sky = skyA.map((a, i) => skyB[i] + (a - skyB[i]) * k);

  gl.viewport(0, 0, canvas.width, canvas.height);
  gl.clearColor(sky[0], sky[1], sky[2], 1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  gl.enable(gl.DEPTH_TEST); gl.enable(gl.CULL_FACE);
  gl.useProgram(prog);
  gl.enableVertexAttribArray(0); gl.enableVertexAttribArray(1); gl.enableVertexAttribArray(2);
  gl.uniformMatrix4fv(U.uProj, false, M4.perspective(rad(cam.fov), canvas.width / canvas.height, 0.1, 200));
  gl.uniformMatrix4fv(U.uView, false, M4.lookAt(eye, cam.target, [0, 1, 0]));
  gl.uniform3fv(U.uEye, eye); gl.uniform3fv(U.uLightDir, sunDir); gl.uniform3fv(U.uLightColor, sunCol);
  gl.uniform3fv(U.uSky, [0.62, 0.70, 0.82]); gl.uniform3fv(U.uGround, [0.42, 0.38, 0.33]);
  gl.uniform1f(U.uAmbient, 0.55 + 0.25 * k); gl.uniform3fv(U.uFogColor, sky); gl.uniform1f(U.uFog, 0.011);
  gl.uniform1i(U.uTex, 0);
  gl.activeTexture(gl.TEXTURE0);
  for (const o of objects) draw(o.inst.root);
  requestAnimationFrame(frame);
}

// tree (hierarchical model)
function treeHTML(n, depth = 0) {
  const label = `<b>${n.name}</b>${n.prims.length ? ' <i>(mesh)</i>' : ''}`;
  if (!n.children.length) return `<li>${label}</li>`;
  return `<li><details ${depth < 2 ? 'open' : ''}><summary>${label}</summary><ul>${n.children.map(c => treeHTML(c, depth + 1)).join('')}</ul></details></li>`;
}
function showTree() {
  const el = document.getElementById('tree');
  el.innerHTML = `<ul><li><details open><summary><b>World</b> (scene root)</summary><ul>` +
    objects.map(o => treeHTML(o.inst.root, 1)).join('') + `</ul></details></li></ul>`;
}

(async () => {
  try {
    const cache = {};
    for (const p of PLACEMENT) {
      status.textContent = `Memuat ${p.file} ...`;
      cache[p.file] = cache[p.file] || await loadGLB(gl, p.file);
      objects.push({ id: p.id, inst: instantiate(cache[p.file], p.id), pos: p.pos, yaw: p.yaw || 0, scale: p.scale || 1 });
    }
    status.textContent = '';
    showTree();
    requestAnimationFrame(frame);
    window.__ready = true;
  } catch (e) {
    status.textContent = 'Gagal memuat: ' + e.message + ' — jalankan lewat server lokal (python3 -m http.server 8000), bukan file://';
    console.error(e);
  }
})();
