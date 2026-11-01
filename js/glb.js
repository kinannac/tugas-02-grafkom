// Loader GLB 2.0 minimal untuk WebGL1 (tanpa library).
// Mendukung: node hierarchy (TRS), mesh POSITION/NORMAL/TEXCOORD_0 + indices uint16,
// material baseColorFactor + baseColorTexture (PNG tertanam).

const isPOT = n => (n & (n - 1)) === 0;
const lin2srgb = c => Math.pow(c, 1 / 2.2);   // viewer bekerja di ruang sRGB sederhana (tanpa gamma pass)

async function loadGLB(gl, url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  const buf = await res.arrayBuffer();
  const dv = new DataView(buf);
  if (dv.getUint32(0, true) !== 0x46546C67) throw new Error(url + ' bukan file GLB');
  const jsonLen = dv.getUint32(12, true);
  const json = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 20, jsonLen)));
  const binOff = 20 + jsonLen + 8;

  const view = i => json.bufferViews[i];
  const typed = (ai, Ctor, comps) => {
    const a = json.accessors[ai], v = view(a.bufferView);
    return new Ctor(buf, binOff + v.byteOffset + (a.byteOffset || 0), a.count * comps);
  };
  const makeBuf = (target, data) => {
    const b = gl.createBuffer(); gl.bindBuffer(target, b); gl.bufferData(target, data, gl.STATIC_DRAW); return b;
  };

  // --- texture
  const textures = [];
  for (const t of json.textures || []) {
    const img = json.images[t.source], v = view(img.bufferView);
    const blob = new Blob([new Uint8Array(buf, binOff + v.byteOffset, v.byteLength)], { type: img.mimeType });
    const bmp = await createImageBitmap(blob);
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, bmp);
    if (isPOT(bmp.width) && isPOT(bmp.height)) {
      gl.generateMipmap(gl.TEXTURE_2D);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT);
    } else {
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    }
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    const aniso = gl.getExtension('EXT_texture_filter_anisotropic');
    if (aniso) gl.texParameterf(gl.TEXTURE_2D, aniso.TEXTURE_MAX_ANISOTROPY_EXT, 8);
    textures.push(tex);
  }

  // --- material
  const materials = (json.materials || []).map(m => {
    const p = m.pbrMetallicRoughness || {}, c = p.baseColorFactor || [1, 1, 1, 1];
    return {
      name: m.name,
      color: [lin2srgb(c[0]), lin2srgb(c[1]), lin2srgb(c[2]), c[3]],
      tex: p.baseColorTexture ? textures[p.baseColorTexture.index] : null,
      spec: (1 - (p.roughnessFactor ?? 1)) * 0.5,
    };
  });

  // --- mesh -> primitif GPU
  const meshes = (json.meshes || []).map(m => m.primitives.map(p => {
    const A = p.attributes, idxAcc = json.accessors[p.indices];
    return {
      pos: makeBuf(gl.ARRAY_BUFFER, typed(A.POSITION, Float32Array, 3)),
      nrm: makeBuf(gl.ARRAY_BUFFER, typed(A.NORMAL, Float32Array, 3)),
      uv: makeBuf(gl.ARRAY_BUFFER, typed(A.TEXCOORD_0, Float32Array, 2)),
      idx: makeBuf(gl.ELEMENT_ARRAY_BUFFER, typed(p.indices, Uint16Array, 1)),
      count: idxAcc.count,
      mat: materials[p.material],
    };
  }));

  // --- node tree (definisi, belum diinstansiasi)
  const defOf = i => {
    const n = json.nodes[i];
    return {
      name: n.name, t: n.translation || [0, 0, 0], q: n.rotation || [0, 0, 0, 1], s: n.scale || [1, 1, 1],
      prims: n.mesh !== undefined ? meshes[n.mesh] : [], children: (n.children || []).map(defOf),
    };
  };
  const roots = json.scenes[json.scene || 0].nodes.map(defOf);
  return { url, root: roots[0] };
}

// Buat salinan pohon node sehingga satu asset bisa dipakai berkali-kali (mis. 6 pohon).
// Buffer GPU dipakai bersama; yang disalin hanya transformasi lokal (t, q, s).
function instantiate(asset, name) {
  const byName = {};
  const clone = (d, parent) => {
    const n = { name: d.name, t: [...d.t], q: [...d.q], s: [...d.s], prims: d.prims, parent,
                children: [], local: new Float32Array(16), world: new Float32Array(16) };
    byName[n.name] = n;
    n.children = d.children.map(c => clone(c, n));
    return n;
  };
  const root = clone(asset.root, null);
  if (name) { delete byName[root.name]; root.name = name; byName[name] = root; }
  return { root, node: byName };
}
