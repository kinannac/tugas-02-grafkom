#!/usr/bin/env python3
"""
Generator model 3D (GLB) untuk scene InfinITS Park - ITS.
Semua model dibuat dari primitif (box, silinder, elipsoid, extrude) lalu
disusun sebagai pohon node (hierarki) dan ditulis ke GLB 2.0.

Konvensi:  satuan meter, Y atas, model karakter menghadap +Z.
Jalankan:  python3 tools/build_models.py
"""
import io, json, math, os, struct
from functools import reduce
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'models')
os.makedirs(OUT, exist_ok=True)

# ----------------------------------------------------------------- matriks
def T(x, y, z):
    m = np.eye(4); m[:3, 3] = (x, y, z); return m
def Rx(d):
    a = math.radians(d); c, s = math.cos(a), math.sin(a)
    m = np.eye(4); m[1, 1] = c; m[1, 2] = -s; m[2, 1] = s; m[2, 2] = c; return m
def Ry(d):
    a = math.radians(d); c, s = math.cos(a), math.sin(a)
    m = np.eye(4); m[0, 0] = c; m[0, 2] = s; m[2, 0] = -s; m[2, 2] = c; return m
def Rz(d):
    a = math.radians(d); c, s = math.cos(a), math.sin(a)
    m = np.eye(4); m[0, 0] = c; m[0, 1] = -s; m[1, 0] = s; m[1, 1] = c; return m
def Sc(x, y, z): return np.diag([x, y, z, 1.0])
def mm(*ms): return reduce(np.dot, ms)

def qaxis(axis, deg):
    a = np.array(axis, float); a /= np.linalg.norm(a)
    h = math.radians(deg) / 2
    return (*(a * math.sin(h)), math.cos(h))
def qmul(a, b):
    x1, y1, z1, w1 = a; x2, y2, z2, w2 = b
    return (w1*x2 + x1*w2 + y1*z2 - z1*y2, w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2, w1*w2 - x1*x2 - y1*y2 - z1*z2)

# --------------------------------------------------------------- geometri
class Geo:
    def __init__(s): s.P = []; s.N = []; s.UV = []; s.I = []; s.n = 0
    def add(s, prim, M=None):
        P, N, UV, I = prim
        P = np.asarray(P, float); N = np.asarray(N, float)
        if M is not None:
            A = M[:3, :3]
            P = P @ A.T + M[:3, 3]
            N = N @ np.linalg.inv(A)
            N = N / np.linalg.norm(N, axis=1, keepdims=True)
        s.P.append(P); s.N.append(N); s.UV.append(np.asarray(UV, float))
        s.I.append(np.asarray(I, int) + s.n); s.n += len(P)
        return s
    def arrays(s):
        P = np.concatenate(s.P); N = np.concatenate(s.N); UV = np.concatenate(s.UV)
        tri = np.concatenate(s.I).reshape(-1, 3).copy()
        p0, p1, p2 = P[tri[:, 0]], P[tri[:, 1]], P[tri[:, 2]]
        gn = np.cross(p1 - p0, p2 - p0)
        vn = N[tri[:, 0]] + N[tri[:, 1]] + N[tri[:, 2]]
        flip = (gn * vn).sum(1) < 0
        tri[flip] = tri[flip][:, [0, 2, 1]]            # winding CCW sesuai normal
        tri = tri[np.linalg.norm(gn, axis=1) > 1e-12]  # buang segitiga degenerate
        return (P.astype(np.float32), N.astype(np.float32), UV.astype(np.float32),
                tri.astype(np.uint32).reshape(-1))

def cat(*prims):
    g = Geo()
    for p in prims: g.add(p)
    P = np.concatenate(g.P); N = np.concatenate(g.N); UV = np.concatenate(g.UV)
    return P, N, UV, np.concatenate(g.I)

def box(w, h, d, tile=None):
    hx, hy, hz = w / 2, h / 2, d / 2
    faces = [((0, 0, 1), [(-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)], (w, h)),
             ((0, 0, -1), [(hx, -hy, -hz), (-hx, -hy, -hz), (-hx, hy, -hz), (hx, hy, -hz)], (w, h)),
             ((1, 0, 0), [(hx, -hy, hz), (hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz)], (d, h)),
             ((-1, 0, 0), [(-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, hz), (-hx, hy, -hz)], (d, h)),
             ((0, 1, 0), [(-hx, hy, hz), (hx, hy, hz), (hx, hy, -hz), (-hx, hy, -hz)], (w, d)),
             ((0, -1, 0), [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz)], (w, d))]
    P = []; N = []; UV = []; I = []
    for nrm, c, (fw, fh) in faces:
        b = len(P); P += c; N += [nrm] * 4
        su, sv = (fw / tile, fh / tile) if tile else (1, 1)
        UV += [(0, sv), (su, sv), (su, 0), (0, 0)]
        I += [b, b + 1, b + 2, b, b + 2, b + 3]
    return P, N, UV, I

def cyl(r0, r1, h, seg=16, caps=True):
    """silinder/kerucut: alas di y=0 (radius r0), atas di y=h (radius r1)."""
    P = []; N = []; UV = []; I = []
    slope = (r0 - r1) / h
    for k in range(seg + 1):
        a = 2 * math.pi * k / seg; c, s = math.cos(a), math.sin(a)
        n = np.array([c, slope, s]); n /= np.linalg.norm(n)
        P += [(r0 * c, 0, r0 * s), (r1 * c, h, r1 * s)]; N += [n, n]
        UV += [(k / seg, 1), (k / seg, 0)]
    for k in range(seg):
        i = 2 * k; I += [i, i + 2, i + 1, i + 1, i + 2, i + 3]
    for r, y, ny in ((r0, 0, -1), (r1, h, 1)):
        if r <= 1e-6 or not caps: continue
        b = len(P); P.append((0, y, 0)); N.append((0, ny, 0)); UV.append((0.5, 0.5))
        for k in range(seg + 1):
            a = 2 * math.pi * k / seg
            P.append((r * math.cos(a), y, r * math.sin(a))); N.append((0, ny, 0))
            UV.append((0.5 + 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a)))
        for k in range(seg): I += [b, b + 1 + k, b + 2 + k]
    return P, N, UV, I

def sph(rx, ry, rz, seg=20, rings=12):
    P = []; N = []; UV = []; I = []
    for i in range(rings + 1):
        phi = math.pi * i / rings
        for j in range(seg + 1):
            th = 2 * math.pi * j / seg
            x = math.sin(phi) * math.cos(th); y = math.cos(phi); z = math.sin(phi) * math.sin(th)
            P.append((x * rx, y * ry, z * rz))
            n = np.array([x / rx, y / ry, z / rz]); N.append(n / np.linalg.norm(n))
            UV.append((j / seg, i / rings))
    for i in range(rings):
        for j in range(seg):
            a = i * (seg + 1) + j; b = a + seg + 1
            I += [a, b, a + 1, a + 1, b, b + 1]
    return P, N, UV, I

def plane(x0, x1, z0, z1, y=0.0, tile=2.0):
    P = [(x0, y, z1), (x1, y, z1), (x1, y, z0), (x0, y, z0)]
    UV = [(x0 / tile, z1 / tile), (x1 / tile, z1 / tile), (x1 / tile, z0 / tile), (x0 / tile, z0 / tile)]
    return P, [(0, 1, 0)] * 4, UV, [0, 1, 2, 0, 2, 3]

def triangulate(poly):
    P = [tuple(p) for p in poly]; n = len(P)
    area = sum(P[i][0] * P[(i + 1) % n][1] - P[(i + 1) % n][0] * P[i][1] for i in range(n)) / 2
    idx = list(range(n))
    if area < 0: idx.reverse()
    cr = lambda a, b, c: (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    inside = lambda p, a, b, c: cr(a, b, p) >= -1e-12 and cr(b, c, p) >= -1e-12 and cr(c, a, p) >= -1e-12
    tris = []
    while len(idx) > 3:
        m = len(idx); found = False
        for k in range(m):
            a, b, c = idx[k - 1], idx[k], idx[(k + 1) % m]
            if cr(P[a], P[b], P[c]) <= 1e-12: continue
            if any(inside(P[j], P[a], P[b], P[c]) for j in idx if j not in (a, b, c)): continue
            tris.append((a, b, c)); idx.pop(k); found = True; break
        if not found: idx.pop(0)
    tris.append(tuple(idx))
    return tris

def extrude_parts(poly, depth, uv=None):
    """poly 2D (x,y) -> prisma z 0..depth. Return (muka_depan, sisa)."""
    poly = np.array(poly, float); n = len(poly)
    area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
    if area < 0: poly = poly[::-1]
    uv = uv or (lambda x, y: (x, y))
    tris = [list(t) for t in triangulate(poly)]
    front = ([(x, y, depth) for x, y in poly], [(0, 0, 1)] * n, [uv(x, y) for x, y in poly],
             np.array(tris).reshape(-1))
    back = ([(x, y, 0) for x, y in poly], [(0, 0, -1)] * n, [uv(x, y) for x, y in poly],
            np.array(tris).reshape(-1))
    sp = []; sn = []; suv = []; si = []
    for i in range(n):
        a = poly[i]; b = poly[(i + 1) % n]; e = b - a
        nn = np.array([e[1], -e[0], 0.0]); nn /= np.linalg.norm(nn)
        base = len(sp)
        sp += [(a[0], a[1], 0), (b[0], b[1], 0), (b[0], b[1], depth), (a[0], a[1], depth)]
        sn += [nn] * 4; suv += [(0, 0), (1, 0), (1, 1), (0, 1)]
        si += [base, base + 1, base + 2, base, base + 2, base + 3]
    return front, cat(back, (sp, sn, suv, si))

def extrude(poly, depth, uv=None):
    f, r = extrude_parts(poly, depth, uv); return cat(f, r)

# ------------------------------------------------------- tekstur prosedural
def pfield(size, sx, sy=None, seed=0):
    sy = sx if sy is None else sy
    a = np.random.default_rng(seed).normal(size=(size, size))
    fx = np.fft.fftfreq(size)[None, :]; fy = np.fft.fftfreq(size)[:, None]
    k = np.exp(-2 * np.pi ** 2 * ((sx * fx) ** 2 + (sy * fy) ** 2))
    b = np.real(np.fft.ifft2(np.fft.fft2(a) * k))
    return (b - b.mean()) / (b.std() + 1e-9)

def to_img(arr): return Image.fromarray(np.clip(arr, 0, 255).astype('uint8'))

def tex_concrete(base=(125, 125, 115), amp=9, seed=1, size=256):
    f = 0.7 * pfield(size, 1.2, seed=seed) + 0.9 * pfield(size, 7, seed=seed + 1) + 0.3 * pfield(size, 0.5, seed=seed + 2)
    return to_img(np.array(base)[None, None, :] + f[..., None] * amp)

def tex_organic(base, amp, seed, size=256, sx=1.5, sy=None):
    f = pfield(size, sx, sy, seed) + 0.6 * pfield(size, 5, seed=seed + 7)
    return to_img(np.array(base)[None, None, :] * (1 + f[..., None] * amp))

def tex_bricks(palette, mortar, size=512, cols=8, rows=16, gap=3, seed=3):
    r = np.random.default_rng(seed)
    img = Image.new('RGB', (size, size), mortar); d = ImageDraw.Draw(img)
    bw, bh = size // cols, size // rows
    for row in range(rows):
        off = bw // 2 if row % 2 else 0
        for c in range(-1, cols + 1):
            col = np.array(palette[r.integers(len(palette))], float) + r.normal(0, 5)
            x0 = c * bw + off; y0 = row * bh
            d.rectangle([x0 + gap, y0 + gap, x0 + bw - 1, y0 + bh - 1], fill=tuple(int(v) for v in np.clip(col, 0, 255)))
    a = np.asarray(img, float) * (1 + 0.05 * pfield(size, 1.0, seed=seed)[..., None])
    return to_img(a)

def tex_fur(size=256):
    y = np.arange(size)[:, None]
    n = pfield(size, 6, seed=5)
    st = np.sin(y / size * 2 * np.pi * 7 + n * 0.9)
    m = np.clip((st - 0.1) * 3, 0, 1)[..., None]
    base = np.array([226, 142, 62.]); dark = np.array([142, 74, 30.])
    col = (base * (1 - m) + dark * m) * (1 + 0.06 * pfield(size, 0.8, seed=9))[..., None]
    return to_img(col)

def font(bold=True, italic=False, size=40):
    name = 'DejaVuSans' + ('-BoldOblique' if bold and italic else '-Bold' if bold else '-Oblique' if italic else '')
    return ImageFont.truetype(f'/usr/share/fonts/truetype/dejavu/{name}.ttf', size)

SIGN_W, SIGN_H = 3.9, 0.98
SIGN_POLY = [(0.03, 0.0), (1.0, 0.0), (1.0, 1.0), (0.53, 1.0), (0.45, 0.78),
             (0.25, 0.38), (0.09, 0.27), (0.0, 0.12)]   # koordinat normal (u,v) v ke atas

def tex_sign():
    W, H = 1024, 256
    img = Image.new('RGB', (W, H), (238, 238, 236)); d = ImageDraw.Draw(img)
    d.polygon([(u * W, (1 - v) * H) for u, v in SIGN_POLY], outline=(205, 205, 205))
    d.text((128, 190), 'SUPPORTED BY', font=font(True, False, 24), fill=(40, 40, 52))
    d.text((700, 16), 'ITS', font=font(True, True, 96), fill=(36, 74, 168))
    d.text((700, 112), 'TEKNO', font=font(True, False, 58), fill=(34, 34, 44))
    d.text((700, 168), 'SAINS', font=font(True, False, 58), fill=(34, 34, 44))
    return img

# ---------------------------------------------------------------- scene graph
def srgb2lin(c): return [float(v) ** 2.2 for v in c]

class Mat:
    def __init__(s, name, rgb, tex=None, rough=0.9):
        s.name, s.rgb, s.tex, s.rough = name, rgb, tex, rough

class Node:
    def __init__(s, name, t=(0, 0, 0), q=(0, 0, 0, 1), sc=(1, 1, 1)):
        s.name, s.t, s.q, s.s = name, tuple(t), tuple(q), tuple(sc)
        s.parts = {}; s.children = []
    def add(s, c): s.children.append(c); return c

def tree_str(n, pre='', last=True, root=True):
    line = n.name + ('   [mesh]' if n.parts else '')
    out = [line if root else pre + ('└── ' if last else '├── ') + line]
    for i, c in enumerate(n.children):
        out += tree_str(c, pre + ('' if root else ('    ' if last else '│   ')), i == len(n.children) - 1, False)
    return out

def write_glb(path, roots):
    bin_ = bytearray(); views = []; accs = []; meshes = []; nodes = []; mats = []; matidx = {}
    images = []; textures = []; texidx = {}
    def add_view(data, target=None):
        while len(bin_) % 4: bin_.append(0)
        v = {"buffer": 0, "byteOffset": len(bin_), "byteLength": len(data)}
        if target: v["target"] = target
        bin_.extend(data); views.append(v); return len(views) - 1
    def add_acc(arr, ctype, atype, target, minmax=False):
        a = {"bufferView": add_view(arr.tobytes(), target), "componentType": ctype, "count": int(len(arr)), "type": atype}
        if minmax: a["min"] = arr.min(0).tolist(); a["max"] = arr.max(0).tolist()
        accs.append(a); return len(accs) - 1
    def get_mat(m):
        if m in matidx: return matidx[m]
        d = {"name": m.name, "doubleSided": False,
             "pbrMetallicRoughness": {"baseColorFactor": srgb2lin(m.rgb) + [1.0], "metallicFactor": 0.0, "roughnessFactor": m.rough}}
        if m.tex is not None:
            if id(m.tex) not in texidx:
                bio = io.BytesIO(); m.tex.save(bio, 'PNG')
                images.append({"bufferView": add_view(bio.getvalue()), "mimeType": "image/png"})
                textures.append({"sampler": 0, "source": len(images) - 1})
                texidx[id(m.tex)] = len(textures) - 1
            d["pbrMetallicRoughness"]["baseColorTexture"] = {"index": texidx[id(m.tex)]}
        mats.append(d); matidx[m] = len(mats) - 1; return matidx[m]
    def add_node(n):
        idx = len(nodes); nodes.append(None)
        d = {"name": n.name}
        if any(n.t): d["translation"] = [round(float(v), 5) for v in n.t]
        if n.q != (0, 0, 0, 1): d["rotation"] = [round(float(v), 6) for v in n.q]
        if n.s != (1, 1, 1): d["scale"] = list(n.s)
        if n.parts:
            prims = []
            for m, g in n.parts.items():
                P, N, UV, I = g.arrays()
                assert len(P) < 65535, (n.name, len(P))
                prims.append({"attributes": {"POSITION": add_acc(P, 5126, "VEC3", 34962, True),
                                             "NORMAL": add_acc(N, 5126, "VEC3", 34962),
                                             "TEXCOORD_0": add_acc(UV, 5126, "VEC2", 34962)},
                              "indices": add_acc(I.astype(np.uint16), 5123, "SCALAR", 34963),
                              "material": get_mat(m), "mode": 4})
            meshes.append({"name": n.name, "primitives": prims}); d["mesh"] = len(meshes) - 1
        ch = [add_node(c) for c in n.children]
        if ch: d["children"] = ch
        nodes[idx] = d; return idx
    root_ids = [add_node(r) for r in roots]
    js = {"asset": {"version": "2.0", "generator": "tugas2-its build_models.py"}, "scene": 0,
          "scenes": [{"nodes": root_ids}], "nodes": nodes, "meshes": meshes, "materials": mats,
          "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": len(bin_)}]}
    if textures:
        js["textures"] = textures; js["images"] = images
        js["samplers"] = [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}]
    jb = json.dumps(js, separators=(',', ':')).encode()
    jb += b' ' * (-len(jb) % 4)
    bb = bytes(bin_) + b'\0' * (-len(bin_) % 4)
    with open(path, 'wb') as f:
        f.write(struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(jb) + 8 + len(bb)))
        f.write(struct.pack('<II', len(jb), 0x4E4F534A)); f.write(jb)
        f.write(struct.pack('<II', len(bb), 0x004E4942)); f.write(bb)
    print(f'  {os.path.basename(path):22s} {os.path.getsize(path)/1024:7.1f} KB  nodes={len(nodes)} meshes={len(meshes)} mats={len(mats)}')

def G(prim, M=None):
    g = Geo(); g.add(prim, M); return g
def acc(*items):
    g = Geo()
    for prim, M in items: g.add(prim, M)
    return g

# =========================================================== MATERIAL
M_CONC_WALL = Mat('concrete_wall', (1, 1, 1), tex_concrete((118, 118, 108), 8, 1), 0.95)
M_CONC_LIGHT = Mat('concrete_light', (1, 1, 1), tex_concrete((160, 158, 150), 7, 11), 0.95)
M_CONC_WALK = Mat('concrete_walk', (1, 1, 1), tex_concrete((178, 176, 170), 6, 21), 0.95)
M_BLUE = Mat('letter_blue', (0.20, 0.35, 0.72), None, 0.55)
M_YELLOW = Mat('letter_yellow', (0.96, 0.78, 0.13), None, 0.55)
M_METAL = Mat('metal_dark', (0.28, 0.28, 0.31), None, 0.5)
M_BLACK = Mat('black', (0.05, 0.05, 0.06), None, 0.6)
M_SIGN_FACE = Mat('sign_face', (1, 1, 1), tex_sign(), 0.5)
M_SIGN_SIDE = Mat('sign_side', (0.92, 0.92, 0.9), None, 0.5)
M_BRICK = Mat('paving_red', (1, 1, 1), tex_bricks([(166, 88, 70), (158, 82, 66), (176, 96, 78), (150, 80, 68)], (112, 98, 92)), 0.9)
M_PAVER = Mat('paving_grey', (1, 1, 1), tex_bricks([(150, 144, 136), (162, 154, 144), (138, 134, 128), (156, 140, 130)], (104, 100, 94), seed=8), 0.9)
M_GRASS = Mat('grass', (1, 1, 1), tex_organic((84, 128, 60), 0.18, 31), 1.0)
M_BARK = Mat('bark', (1, 1, 1), tex_organic((96, 76, 62), 0.28, 41, sx=0.8, sy=7), 1.0)
LEAF_TEX = tex_organic((58, 108, 46), 0.30, 51, sx=1.2)
M_LEAF_A = Mat('leaf_a', (1.0, 1.0, 1.0), LEAF_TEX, 1.0)
M_LEAF_B = Mat('leaf_b', (0.82, 1.0, 0.72), LEAF_TEX, 1.0)
M_FUR = Mat('cat_fur_tabby', (1, 1, 1), tex_fur(), 1.0)
M_FUR_W = Mat('cat_fur_white', (0.94, 0.92, 0.88), None, 1.0)
M_PINK = Mat('cat_pink', (0.92, 0.58, 0.58), None, 0.8)
M_EYE = Mat('cat_eye', (0.45, 0.78, 0.30), None, 0.3)
M_SKIN = Mat('skin', (0.86, 0.66, 0.50), None, 0.8)
M_HAIR = Mat('hair', (0.07, 0.06, 0.06), None, 0.7)
M_SHIRT = Mat('jacket_blue', (0.16, 0.34, 0.68), None, 0.85)
M_PANTS = Mat('pants_dark', (0.14, 0.15, 0.22), None, 0.9)
M_SHOE = Mat('shoe_white', (0.92, 0.92, 0.92), None, 0.7)
M_BAG = Mat('backpack_yellow', (0.93, 0.72, 0.10), None, 0.8)

# =========================================================== SIGN (InfinITS Park)
TK, DP, XH, CAP, ASC = 0.28, 0.28, 1.0, 1.2, 1.4

def stroke(p0, p1, th):
    p0 = np.array(p0, float); p1 = np.array(p1, float)
    d = (p1 - p0) / np.linalg.norm(p1 - p0); n = np.array([-d[1], d[0]]) * th / 2
    return [p0 - n, p1 - n, p1 + n, p0 + n]

def glyph(ch):
    g = Geo()
    def bar(x0, y0, x1, y1):
        g.add(box(x1 - x0, y1 - y0, DP), T((x0 + x1) / 2, (y0 + y1) / 2, 0))
    def poly(pts, dz=0.0):
        d = DP - dz; g.add(extrude(pts, d), T(0, 0, -d / 2))
    def arc(cx, cy, r0, r1, a0, a1, seg=16):
        ang = np.radians(np.linspace(a0, a1, seg)); angr = ang[::-1]
        poly([(cx + r1 * math.cos(a), cy + r1 * math.sin(a)) for a in ang] +
             [(cx + r0 * math.cos(a), cy + r0 * math.sin(a)) for a in angr])
    if ch == 'i': bar(0, 0, TK, XH); w = TK
    elif ch == 'n':
        w = 1.15; r1 = w / 2; cy = XH - r1
        bar(0, 0, TK, cy); bar(w - TK, 0, w, cy); arc(w / 2, cy, r1 - TK, r1, 0, 180)
    elif ch == 'f':
        w = 0.72; r1 = 0.43; r0 = r1 - TK; cy = ASC - r1; cx = 0.18 + TK + r0
        bar(0.18, 0, 0.18 + TK, cy); arc(cx, cy, r0, r1, 90, 180)
        bar(cx, ASC - TK, cx + 0.11, ASC)
        bar(0, XH - TK - 0.02, 0.18, XH - 0.02); bar(0.18 + TK, XH - TK - 0.02, 0.66, XH - 0.02)
    elif ch == 'I': bar(0, 0, TK, CAP); w = TK
    elif ch == 'T': w = 0.9; bar(0.31, 0, 0.31 + TK, CAP - TK); bar(0, CAP - TK, w, CAP)
    elif ch == 'S':
        w = 1.05; m = CAP / 2
        bar(0, CAP - TK, w, CAP); bar(0, m - TK / 2, w, m + TK / 2); bar(0, 0, w, TK)
        bar(0, m + TK / 2, TK, CAP - TK); bar(w - TK, TK, w, m - TK / 2)
    elif ch == 'P':
        w = 1.1; ym = 0.55
        bar(0, 0, TK, CAP - TK); bar(0, CAP - TK, w, CAP); bar(TK, ym, w - TK, ym + TK); bar(w - TK, ym, w, CAP - TK)
    elif ch == 'a':
        w = 1.0; ym = 0.40
        bar(0, XH - TK, w, XH); bar(w - TK, 0, w, XH - TK); bar(TK, ym, w - TK, ym + TK)
        bar(0, 0, TK, ym + TK); bar(TK, 0, w - TK, TK)
    elif ch == 'r':
        w = 0.62; bar(0, 0, TK, XH); bar(TK, XH - TK, w, XH); bar(w - TK, XH - 0.32, w, XH - TK)
    elif ch == 'k':
        w = 0.95; bar(0, 0, TK, ASC)
        poly(stroke((0.36, 0.52), (0.86, XH - 0.10), 0.27), 0.012)
        poly(stroke((0.50, 0.62), (0.88, 0.13), 0.27), 0.024)
    return g, w

FEET = {'i': [0.14], 'n': [0.14, 1.01], 'f': [0.32], 'I': [0.14], 'T': [0.45], 'S': [0.3, 0.78],
        'P': [0.14], 'a': [0.3, 0.86], 'r': [0.14], 'k': [0.14]}

def build_sign():
    root = Node('InfinITS_Park_Sign')
    wall = root.add(Node('Wall', t=(0, 0.54, 0)))
    wall.parts[M_CONC_WALL] = G(box(18, 1.12, 0.5, tile=2.0))
    low = root.add(Node('Platform_Lower', t=(-1.75, 0.065, 1.325)))
    low.parts[M_CONC_LIGHT] = G(box(9.7, 0.17, 2.15, tile=2.0))
    up = low.add(Node('Platform_Upper', t=(-0.63, 0.16, -0.475)))
    up.parts[M_CONC_LIGHT] = G(box(4.24, 0.15, 1.2, tile=2.0))
    # huruf
    def letters(groupname, text, mat, x0):
        grp = Node(groupname, t=(0, 1.4, 0)); x = x0; stilts = Geo(); k = 0
        for ch in text:
            g, w = glyph(ch); k += 1
            nd = grp.add(Node(f'Letter_{ch}_{k}', t=(x, 0, 0))); nd.parts[mat] = g
            for fx in FEET[ch]:
                stilts.add(cyl(0.032, 0.032, 0.3, 10), T(x + fx, -0.3, 0))
            x += w + 0.25
        return grp, x - 0.25, stilts
    g1, xe, s1 = letters('Letters_InfinITS', 'infinITS', M_BLUE, -6.5)
    g2, xe2, s2 = letters('Letters_Park', 'Park', M_YELLOW, xe + 0.82)
    root.add(g1); root.add(g2)
    st = g1.add(Node('Stilts_InfinITS')); st.parts[M_METAL] = s1
    st2 = g2.add(Node('Stilts_Park')); st2.parts[M_METAL] = s2
    spots = root.add(Node('Spotlights', t=(0, 1.15, 0.12)))
    sg = Geo()
    for xx in np.arange(-6.2, xe2, 1.25): sg.add(box(0.14, 0.1, 0.14), T(xx, 0, 0))
    spots.parts[M_BLACK] = sg
    # papan ITS TEKNO SAINS
    board = root.add(Node('Signboard_ITS', t=(3.5, 0.22, 0.25)))
    pts = [(u * SIGN_W, v * SIGN_H) for u, v in SIGN_POLY]
    front, rest = extrude_parts(pts, 0.1, uv=lambda x, y: (x / SIGN_W, 1 - y / SIGN_H))
    board.parts[M_SIGN_FACE] = G(front); board.parts[M_SIGN_SIDE] = G(rest)
    return root

def build_ground():
    r = Node('Ground')
    n = r.add(Node('Grass_Behind_Wall')); n.parts[M_GRASS] = G(plane(-45, 45, -45, 0.25, 0.0, 3.0))
    n = r.add(Node('Paving_Red')); n.parts[M_BRICK] = G(plane(-45, 45, 0.25, 3.6, 0.0, 2.0))
    n = r.add(Node('Paving_Grey')); n.parts[M_PAVER] = G(plane(-45, 45, 3.6, 8.0, 0.0, 2.0))
    n = r.add(Node('Curb', t=(0, 0.06, 8.175))); n.parts[M_CONC_LIGHT] = G(box(90, 0.16, 0.35, tile=2.0))
    n = r.add(Node('Sidewalk_Concrete')); n.parts[M_CONC_WALK] = G(plane(-45, 45, 8.35, 30, 0.0, 2.0))
    return r

def build_tree():
    r = Node('Tree')
    trunk = r.add(Node('Trunk')); trunk.parts[M_BARK] = G(cyl(0.40, 0.26, 4.0, 14))
    for i, yaw in enumerate((20, 110, 200, 290), 1):
        b = trunk.add(Node(f'Branch_{i}', t=(0, 3.7, 0), q=qmul(qaxis((0, 1, 0), yaw), qaxis((0, 0, 1), -38))))
        b.parts[M_BARK] = G(cyl(0.17, 0.09, 2.4, 10))
    can = r.add(Node('Canopy', t=(0, 6.1, 0)))
    blobs = [('Blob_Center', (0, 0.2, 0), (3.6, 1.7, 3.6), M_LEAF_A)]
    for i in range(6):
        a = math.radians(i * 60 + 15)
        blobs.append((f'Blob_{i+1}', (3.0 * math.cos(a), -0.35 + 0.25 * (i % 2), 3.0 * math.sin(a)),
                      (2.3, 1.25, 2.3), M_LEAF_B if i % 2 else M_LEAF_A))
    for name, pos, rad, mat in blobs:
        b = can.add(Node(name, t=pos)); b.parts[mat] = G(sph(*rad, seg=18, rings=10))
    return r

def build_cat():
    cat_ = Node('Cat')
    body = cat_.add(Node('Cat_Body', t=(0, 0.29, 0)))
    body.parts[M_FUR] = G(sph(0.095, 0.23, 0.105, 20, 14), Rx(90))
    body.parts[M_FUR_W] = G(sph(0.06, 0.05, 0.07), T(0, -0.045, 0.14))
    head = body.add(Node('Cat_Head', t=(0, 0.075, 0.22)))
    head.parts[M_FUR] = G(sph(0.085, 0.075, 0.075), T(0, 0.045, 0.05))
    head.parts[M_FUR_W] = G(sph(0.04, 0.03, 0.035), T(0, 0.012, 0.105))
    head.parts[M_PINK] = G(sph(0.011, 0.009, 0.009), T(0, 0.033, 0.14))
    for side, sx in (('L', 1), ('R', -1)):
        e = head.add(Node(f'Cat_Eye_{side}', t=(sx * 0.04, 0.07, 0.108)))
        e.parts[M_EYE] = G(sph(0.014, 0.014, 0.009))
        e.parts[M_BLACK] = G(sph(0.0065, 0.011, 0.005), T(0, 0, 0.007))
        ear = head.add(Node(f'Cat_Ear_{side}', t=(sx * 0.052, 0.098, 0.03), q=qaxis((0, 0, 1), -sx * 14)))
        ear.parts[M_FUR] = G(cyl(0.036, 0.0, 0.075, 8, caps=True))
        ear.parts[M_PINK] = G(cyl(0.022, 0.0, 0.05, 8), T(0, 0.004, 0.014))
    t1 = body.add(Node('Cat_Tail1', t=(0, 0.035, -0.215), q=qaxis((1, 0, 0), 34)))
    t1.parts[M_FUR] = acc((cyl(0.027, 0.024, 0.13, 10), Rx(-90)), (sph(0.027, 0.027, 0.027, 10, 8), None))
    t2 = t1.add(Node('Cat_Tail2', t=(0, 0, -0.13), q=qaxis((1, 0, 0), 14)))
    t2.parts[M_FUR] = acc((cyl(0.024, 0.021, 0.12, 10), Rx(-90)), (sph(0.024, 0.024, 0.024, 10, 8), None))
    t3 = t2.add(Node('Cat_Tail3', t=(0, 0, -0.12), q=qaxis((1, 0, 0), 10)))
    t3.parts[M_FUR] = acc((cyl(0.021, 0.015, 0.11, 10), Rx(-90)), (sph(0.021, 0.021, 0.021, 10, 8), None))
    t3.parts[M_FUR_W] = G(sph(0.016, 0.016, 0.02, 10, 8), T(0, 0, -0.115))
    for nm, sx, sz in (('FL', 1, 1), ('FR', -1, 1), ('BL', 1, -1), ('BR', -1, -1)):
        up = body.add(Node(f'Cat_Leg_{nm}_Upper', t=(sx * 0.068, -0.045, sz * 0.15)))
        items = [(cyl(0.034, 0.026, 0.12, 10), Rx(180)), (sph(0.036, 0.036, 0.036, 10, 8), None)]
        if sz < 0: items.append((sph(0.048, 0.08, 0.07, 12, 8), T(0, -0.035, 0)))
        up.parts[M_FUR] = acc(*items)
        lo = up.add(Node(f'Cat_Leg_{nm}_Lower', t=(0, -0.12, 0)))
        lo.parts[M_FUR] = acc((cyl(0.024, 0.019, 0.11, 10), Rx(180)), (sph(0.026, 0.026, 0.026, 10, 8), None))
        lo.parts[M_FUR_W] = G(sph(0.03, 0.02, 0.04, 10, 8), T(0, -0.105, 0.012))
    return cat_

def build_human():
    h = Node('Human')
    pel = h.add(Node('Human_Pelvis', t=(0, 0.93, 0)))
    pel.parts[M_PANTS] = G(box(0.34, 0.2, 0.21))
    tor = pel.add(Node('Human_Torso', t=(0, 0.08, 0)))
    tor.parts[M_SHIRT] = acc((box(0.34, 0.5, 0.21), T(0, 0.25, 0)), (sph(0.055, 0.055, 0.055, 10, 8), T(0.21, 0.44, 0)),
                             (sph(0.055, 0.055, 0.055, 10, 8), T(-0.21, 0.44, 0)))
    tor.parts[M_SKIN] = G(cyl(0.045, 0.04, 0.09, 12), T(0, 0.49, 0))
    bag = tor.add(Node('Human_Backpack', t=(0, 0.27, -0.175)))
    bag.parts[M_BAG] = G(box(0.31, 0.40, 0.13))
    bag.parts[M_BLACK] = G(box(0.31, 0.04, 0.131), T(0, 0.02, 0))
    head = tor.add(Node('Human_Head', t=(0, 0.52, 0)))
    head.parts[M_SKIN] = acc((sph(0.085, 0.105, 0.095, 18, 12), T(0, 0.115, 0.005)), (sph(0.014, 0.014, 0.014, 8, 6), T(0, 0.095, 0.098)),
                             (sph(0.014, 0.025, 0.02, 8, 6), T(0.087, 0.115, 0)), (sph(0.014, 0.025, 0.02, 8, 6), T(-0.087, 0.115, 0)))
    head.parts[M_HAIR] = acc((sph(0.092, 0.10, 0.102, 18, 12), T(0, 0.145, -0.012)))
    head.parts[M_BLACK] = acc((sph(0.011, 0.011, 0.008, 8, 6), T(0.035, 0.12, 0.092)), (sph(0.011, 0.011, 0.008, 8, 6), T(-0.035, 0.12, 0.092)))
    for side, sx in (('L', 1), ('R', -1)):
        sh = tor.add(Node(f'Human_Shoulder_{side}', t=(sx * 0.21, 0.44, 0)))
        sh.parts[M_SHIRT] = G(cyl(0.05, 0.042, 0.27, 12), Rx(180))
        el = sh.add(Node(f'Human_Elbow_{side}', t=(0, -0.27, 0)))
        el.parts[M_SKIN] = acc((cyl(0.04, 0.034, 0.25, 12), Rx(180)), (sph(0.04, 0.04, 0.04, 10, 8), None))
        wr = el.add(Node(f'Human_Wrist_{side}', t=(0, -0.25, 0)))
        wr.parts[M_SKIN] = G(sph(0.04, 0.055, 0.03, 10, 8), T(0, -0.045, 0))
        hip = pel.add(Node(f'Human_Hip_{side}', t=(sx * 0.095, -0.06, 0)))
        hip.parts[M_PANTS] = acc((cyl(0.082, 0.062, 0.43, 12), Rx(180)), (sph(0.082, 0.082, 0.082, 10, 8), None))
        kn = hip.add(Node(f'Human_Knee_{side}', t=(0, -0.43, 0)))
        kn.parts[M_PANTS] = acc((cyl(0.058, 0.042, 0.40, 12), Rx(180)), (sph(0.06, 0.06, 0.06, 10, 8), None))
        an = kn.add(Node(f'Human_Ankle_{side}', t=(0, -0.40, 0)))
        an.parts[M_SHOE] = G(box(0.095, 0.08, 0.26), T(0, 0, 0.06))
    return h

if __name__ == '__main__':
    models = {'infinits_sign.glb': build_sign(), 'ground.glb': build_ground(), 'tree.glb': build_tree(),
              'cat.glb': build_cat(), 'human.glb': build_human()}
    print('Menulis GLB ->', os.path.abspath(OUT))
    for fn, root in models.items(): write_glb(os.path.join(OUT, fn), [root])
    with open(os.path.join(OUT, 'hierarchy.txt'), 'w') as f:
        for fn, root in models.items():
            f.write(f'## {fn}\n' + '\n'.join(tree_str(root)) + '\n\n')
