# Tugas 2 Grafika Komputer – InfinITS Park (WebGL)

Jalankan: `python3 -m http.server 8000` di folder ini, buka http://localhost:8000
(harus lewat server, tidak bisa klik dua kali index.html karena `fetch` GLB).

## Isi
- `models/*.glb`  – model 3D (sudah ada hierarki node + tekstur tertanam)
- `js/glb.js`     – loader GLB tanpa library (parse JSON+BIN, buat buffer & texture)
- `js/mat4.js`    – matriks 4x4 / quaternion
- `js/main.js`    – scene (penempatan world coordinate), lighting, kamera, animasi
- `tools/build_models.py` – generator model; ubah ukuran/warna lalu jalankan ulang
- `assets/` – foto_asli.jpg (sudah ada), video_asli.mp4 (isi sendiri)

## Cara kerja hierarchical model
Tiap node GLB hanya menyimpan transformasi LOKAL (translation/rotation/scale) terhadap induknya,
dan titik pivot sendi ada di origin node (mis. `Human_Knee_L` ada di lutut).
Setiap frame: `world = parentWorld * local` (lihat `updateWorld` di main.js).
Animasi = ubah `node.q` sendi saja, anak (shin, foot) ikut bergerak otomatis.
Karakter menghadap +Z, kiri = +X.

## Nama node untuk animasi
Human: Human_Pelvis, Human_Torso, Human_Head, Human_Backpack, Human_Shoulder_L/R, Human_Elbow_L/R, Human_Wrist_L/R, Human_Hip_L/R, Human_Knee_L/R, Human_Ankle_L/R
Cat: Cat_Body, Cat_Head, Cat_Ear_L/R, Cat_Eye_L/R, Cat_Tail1-3, Cat_Leg_{FL,FR,BL,BR}_{Upper,Lower}

## Tree scene (world)
World → Sign, Ground, Tree_1..6 (instansiasi tree.glb), Cat, Human

## Tree hierarki per model
## infinits_sign.glb
InfinITS_Park_Sign
├── Wall   [mesh]
├── Platform_Lower   [mesh]
│   └── Platform_Upper   [mesh]
├── Letters_InfinITS
│   ├── Letter_i_1   [mesh]
│   ├── Letter_n_2   [mesh]
│   ├── Letter_f_3   [mesh]
│   ├── Letter_i_4   [mesh]
│   ├── Letter_n_5   [mesh]
│   ├── Letter_I_6   [mesh]
│   ├── Letter_T_7   [mesh]
│   ├── Letter_S_8   [mesh]
│   └── Stilts_InfinITS   [mesh]
├── Letters_Park
│   ├── Letter_P_1   [mesh]
│   ├── Letter_a_2   [mesh]
│   ├── Letter_r_3   [mesh]
│   ├── Letter_k_4   [mesh]
│   └── Stilts_Park   [mesh]
├── Spotlights   [mesh]
└── Signboard_ITS   [mesh]

## ground.glb
Ground
├── Grass_Behind_Wall   [mesh]
├── Paving_Red   [mesh]
├── Paving_Grey   [mesh]
├── Curb   [mesh]
└── Sidewalk_Concrete   [mesh]

## tree.glb
Tree
├── Trunk   [mesh]
│   ├── Branch_1   [mesh]
│   ├── Branch_2   [mesh]
│   ├── Branch_3   [mesh]
│   └── Branch_4   [mesh]
└── Canopy
    ├── Blob_Center   [mesh]
    ├── Blob_1   [mesh]
    ├── Blob_2   [mesh]
    ├── Blob_3   [mesh]
    ├── Blob_4   [mesh]
    ├── Blob_5   [mesh]
    └── Blob_6   [mesh]

## cat.glb
Cat
└── Cat_Body   [mesh]
    ├── Cat_Head   [mesh]
    │   ├── Cat_Eye_L   [mesh]
    │   ├── Cat_Ear_L   [mesh]
    │   ├── Cat_Eye_R   [mesh]
    │   └── Cat_Ear_R   [mesh]
    ├── Cat_Tail1   [mesh]
    │   └── Cat_Tail2   [mesh]
    │       └── Cat_Tail3   [mesh]
    ├── Cat_Leg_FL_Upper   [mesh]
    │   └── Cat_Leg_FL_Lower   [mesh]
    ├── Cat_Leg_FR_Upper   [mesh]
    │   └── Cat_Leg_FR_Lower   [mesh]
    ├── Cat_Leg_BL_Upper   [mesh]
    │   └── Cat_Leg_BL_Lower   [mesh]
    └── Cat_Leg_BR_Upper   [mesh]
        └── Cat_Leg_BR_Lower   [mesh]

## human.glb
Human
└── Human_Pelvis   [mesh]
    ├── Human_Torso   [mesh]
    │   ├── Human_Backpack   [mesh]
    │   ├── Human_Head   [mesh]
    │   ├── Human_Shoulder_L   [mesh]
    │   │   └── Human_Elbow_L   [mesh]
    │   │       └── Human_Wrist_L   [mesh]
    │   └── Human_Shoulder_R   [mesh]
    │       └── Human_Elbow_R   [mesh]
    │           └── Human_Wrist_R   [mesh]
    ├── Human_Hip_L   [mesh]
    │   └── Human_Knee_L   [mesh]
    │       └── Human_Ankle_L   [mesh]
    └── Human_Hip_R   [mesh]
        └── Human_Knee_R   [mesh]
            └── Human_Ankle_R   [mesh]

