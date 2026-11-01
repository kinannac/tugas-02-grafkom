// Utilitas matriks 4x4 column-major (kompatibel dengan gl.uniformMatrix4fv, transpose=false)
const M4 = {
  identity() { const o = new Float32Array(16); o[0] = o[5] = o[10] = o[15] = 1; return o; },

  // out = a * b
  mul(a, b, out = new Float32Array(16)) {
    for (let c = 0; c < 4; c++)
      for (let r = 0; r < 4; r++) {
        let s = 0;
        for (let k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k];
        out[c * 4 + r] = s;
      }
    return out;
  },

  perspective(fovy, aspect, n, f) {
    const t = 1 / Math.tan(fovy / 2), o = new Float32Array(16);
    o[0] = t / aspect; o[5] = t; o[10] = (f + n) / (n - f); o[11] = -1; o[14] = 2 * f * n / (n - f);
    return o;
  },

  lookAt(e, c, up) {
    let zx = e[0] - c[0], zy = e[1] - c[1], zz = e[2] - c[2];
    let l = Math.hypot(zx, zy, zz); zx /= l; zy /= l; zz /= l;
    let xx = up[1] * zz - up[2] * zy, xy = up[2] * zx - up[0] * zz, xz = up[0] * zy - up[1] * zx;
    l = Math.hypot(xx, xy, xz); xx /= l; xy /= l; xz /= l;
    const yx = zy * xz - zz * xy, yy = zz * xx - zx * xz, yz = zx * xy - zy * xx;
    const o = new Float32Array(16);
    o[0] = xx; o[1] = yx; o[2] = zx;
    o[4] = xy; o[5] = yy; o[6] = zy;
    o[8] = xz; o[9] = yz; o[10] = zz;
    o[12] = -(xx * e[0] + xy * e[1] + xz * e[2]);
    o[13] = -(yx * e[0] + yy * e[1] + yz * e[2]);
    o[14] = -(zx * e[0] + zy * e[1] + zz * e[2]);
    o[15] = 1;
    return o;
  },

  // Translate * Rotate(quaternion) * Scale  -> matriks lokal sebuah node
  fromTRS(t, q, s, o = new Float32Array(16)) {
    const [x, y, z, w] = q, xx = x * x, yy = y * y, zz = z * z, xy = x * y, xz = x * z, yz = y * z, wx = w * x, wy = w * y, wz = w * z;
    o[0] = (1 - 2 * (yy + zz)) * s[0]; o[1] = 2 * (xy + wz) * s[0]; o[2] = 2 * (xz - wy) * s[0]; o[3] = 0;
    o[4] = 2 * (xy - wz) * s[1]; o[5] = (1 - 2 * (xx + zz)) * s[1]; o[6] = 2 * (yz + wx) * s[1]; o[7] = 0;
    o[8] = 2 * (xz + wy) * s[2]; o[9] = 2 * (yz - wx) * s[2]; o[10] = (1 - 2 * (xx + yy)) * s[2]; o[11] = 0;
    o[12] = t[0]; o[13] = t[1]; o[14] = t[2]; o[15] = 1;
    return o;
  },

  // inverse-transpose dari 3x3 kiri-atas (untuk transformasi normal)
  normal3(m, o = new Float32Array(9)) {
    const a = (r, c) => m[c * 4 + r];
    const c00 = a(1, 1) * a(2, 2) - a(1, 2) * a(2, 1), c01 = -(a(1, 0) * a(2, 2) - a(1, 2) * a(2, 0)), c02 = a(1, 0) * a(2, 1) - a(1, 1) * a(2, 0);
    const c10 = -(a(0, 1) * a(2, 2) - a(0, 2) * a(2, 1)), c11 = a(0, 0) * a(2, 2) - a(0, 2) * a(2, 0), c12 = -(a(0, 0) * a(2, 1) - a(0, 1) * a(2, 0));
    const c20 = a(0, 1) * a(1, 2) - a(0, 2) * a(1, 1), c21 = -(a(0, 0) * a(1, 2) - a(0, 2) * a(1, 0)), c22 = a(0, 0) * a(1, 1) - a(0, 1) * a(1, 0);
    const d = 1 / (a(0, 0) * c00 + a(0, 1) * c01 + a(0, 2) * c02);
    const C = [[c00, c01, c02], [c10, c11, c12], [c20, c21, c22]];
    for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) o[c * 3 + r] = C[r][c] * d;
    return o;
  },
};

// Quaternion [x,y,z,w]
const Q = {
  axis(ax, deg) { const h = deg * Math.PI / 360, s = Math.sin(h); return [ax[0] * s, ax[1] * s, ax[2] * s, Math.cos(h)]; },
  mul(a, b) {
    return [a[3] * b[0] + a[0] * b[3] + a[1] * b[2] - a[2] * b[1], a[3] * b[1] - a[0] * b[2] + a[1] * b[3] + a[2] * b[0],
            a[3] * b[2] + a[0] * b[1] - a[1] * b[0] + a[2] * b[3], a[3] * b[3] - a[0] * b[0] - a[1] * b[1] - a[2] * b[2]];
  },
  rx(d) { return Q.axis([1, 0, 0], d); }, ry(d) { return Q.axis([0, 1, 0], d); }, rz(d) { return Q.axis([0, 0, 1], d); },
};
