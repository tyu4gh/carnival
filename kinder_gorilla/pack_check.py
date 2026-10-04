"""Do the three gorilla parts fit in the closed Kinder capsule? (real inner profile from
../kinder_butterfly_clip/rhino/kinder_rhino_build.py). Searches orientations / positions, checks
every vertex is >= MARGIN inside the capsule and that the parts do not overlap (manifold3d).
Writes out/packing.json and img/g_packed.png."""
import json, math, os, sys, itertools, random
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation as Rot

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "kinder_butterfly_clip", "rhino"))
import kinder_rhino_build as K

MARGIN = 0.3
OUT = os.path.join(HERE, "out")


def profile(segs, n=40):
    pts = []
    for s in segs:
        if s[0] == 'L':
            a, b = s[1], s[2]
            pts += [(a[0] + (b[0] - a[0]) * t / n, a[1] + (b[1] - a[1]) * t / n) for t in range(n + 1)]
        else:  # arc through 3 points: sample by circumcircle
            (x1, y1), (x2, y2), (x3, y3) = s[1], s[2], s[3]
            d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
            ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / d
            uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / d
            r = math.hypot(x1 - ux, y1 - uy)
            a1, a2, a3 = [math.atan2(y - uy, x - ux) for (x, y) in (s[1], s[2], s[3])]

            def norm(a):
                return a % (2 * math.pi)
            # go from a1 to a3 through a2
            ccw = (norm(a2 - a1) < norm(a3 - a1))
            span = norm(a3 - a1) if ccw else -norm(a1 - a3)
            pts += [(ux + r * math.cos(a1 + span * t / n), uy + r * math.sin(a1 + span * t / n)) for t in range(n + 1)]
    return np.array(pts)


def r_of_z(prof, z):
    """inner radius of a (r, z) wall profile at height z (max r of the profile crossings)"""
    rs = []
    for (r1, z1), (r2, z2) in zip(prof[:-1], prof[1:]):
        if (z1 - z) * (z2 - z) <= 0 and z1 != z2:
            rs.append(r1 + (r2 - r1) * (z - z1) / (z2 - z1))
    return max(rs) if rs else 0.0


BASE = profile(K.egg_base_inner()[:-1])     # drop the closing line along the top
CAP = profile(K.egg_cap_inner()[:-1])
E = K.EGG
Z0, Z1 = E['T'], E['L_TOTAL'] - E['T']
NECK_TOP = E['Z_SEAM'] + E['NECK_H']
ZS = np.linspace(Z0, Z1, 400)
RIN = []
for z in ZS:
    rb = r_of_z(BASE, z) if z <= NECK_TOP else 1e9
    rc = r_of_z(CAP, z) if z >= E['Z_SEAM'] else 1e9
    RIN.append(min(rb, rc))
RIN = np.array(RIN)


def inside(verts):
    z = verts[:, 2]
    if z.min() < Z0 + MARGIN or z.max() > Z1 - MARGIN:
        return False, max(Z0 + MARGIN - z.min(), z.max() - Z1 + MARGIN)
    r = np.hypot(verts[:, 0], verts[:, 1])
    lim = np.interp(z, ZS, RIN) - MARGIN
    worst = (r - lim).max()
    return worst <= 0, worst


import manifold3d as mf
_MF = {}


def to_mf(m):
    return mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices, dtype=np.float32),
                               tri_verts=np.asarray(m.faces, dtype=np.uint32)))


def overlap(a, b):
    """intersection volume of two placed meshes (manifold3d); bounding boxes first"""
    if (a.bounds[1] < b.bounds[0]).any() or (b.bounds[1] < a.bounds[0]).any():
        return 0.0
    return (to_mf(a) ^ to_mf(b)).volume()


def place(m, R, t):
    c = m.copy()
    c.apply_transform(np.vstack([np.hstack([R, np.array(t)[:, None]]), [0, 0, 0, 1]]))
    return c


def main():
    names = ["P1_BODY", "P2_ARMS", "P3_HEAD"]
    meshes = {n: trimesh.load(os.path.join(OUT, n + ".stl")) for n in names}
    for n, m in meshes.items():
        m.apply_translation(-m.bounding_box.centroid)
        print(n, "size", np.round(m.extents, 2), "watertight", m.is_watertight, "vol %.0f" % m.volume)
    random.seed(1)
    rots = [Rot.from_euler('xyz', e, degrees=True).as_matrix()
            for e in itertools.product((0, 90, 180, 270), (0, 90, 180, 270), (0, 90))]
    rng = np.random.default_rng(2)
    zc = (Z0 + Z1) / 2
    best = None
    # body: try orientations that fit centred; then arms / head around it
    body_opts = []
    for R in rots:
        b = place(meshes["P1_BODY"], R, (0, 0, zc))
        ok, w = inside(b.vertices)
        if ok:
            body_opts.append((R, b))
    print("body orientations that fit centred:", len(body_opts))
    for trial in range(4000):
        Rb, _ = body_opts[rng.integers(len(body_opts))]
        Rz = Rot.from_euler('z', rng.uniform(0, 360), degrees=True).as_matrix()
        tb = (rng.uniform(-2, 2), rng.uniform(-2, 2), zc + rng.uniform(-6, 6))
        b = place(meshes["P1_BODY"], Rz @ Rb, tb)
        if not inside(b.vertices)[0]:
            continue
        placed = {"P1_BODY": (Rz @ Rb, tb, b)}
        ok_all = True
        for n in ("P2_ARMS", "P3_HEAD"):
            found = None
            for k in range(400):
                R = Rot.random(random_state=int(rng.integers(1 << 30))).as_matrix() if k % 3 else \
                    Rot.from_euler('z', rng.uniform(0, 360), degrees=True).as_matrix() @ rots[int(rng.integers(len(rots)))]
                t = (rng.uniform(-9, 9), rng.uniform(-9, 9), rng.uniform(Z0 + 5, Z1 - 5))
                m = place(meshes[n], R, t)
                if not inside(m.vertices)[0]:
                    continue
                if any(overlap(m, p[2]) > 1e-3 for p in placed.values()):
                    continue
                found = (R, t, m)
                break
            if found is None:
                ok_all = False
                break
            placed[n] = found
        if ok_all:
            best = placed
            print("PACKING OK after %d trials" % (trial + 1))
            break
    if best is None:
        print("PACKING FAIL")
        return 1
    res = {n: dict(R=np.round(v[0], 6).tolist(), t=list(map(float, v[1])),
                   centre_offset=list(map(float, -trimesh.load(os.path.join(OUT, n + ".stl")).bounding_box.centroid)))
           for n, v in best.items()}
    json.dump(res, open(os.path.join(OUT, "packing.json"), "w"), indent=1)
    for n, v in best.items():
        v[2].export(os.path.join(OUT, "packed_%s.stl" % n))
    # picture
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=(10, 5))
    for i, (el, az) in enumerate(((15, -60), (80, -90))):
        ax = fig.add_subplot(1, 2, i + 1, projection="3d")
        cols = {"P1_BODY": (0.45, 0.42, 0.40), "P2_ARMS": (0.65, 0.55, 0.45), "P3_HEAD": (0.30, 0.28, 0.27)}
        light = np.array([-0.3, -0.5, 0.8]); light /= np.linalg.norm(light)
        for n, v in best.items():
            m = v[2].simplify_quadric_decimation(face_count=6000) if hasattr(v[2], "simplify_quadric_decimation") else v[2]
            sh = 0.45 + 0.55 * np.clip(m.face_normals @ light, 0, 1)
            fc = np.clip(np.array(cols[n])[None] * sh[:, None], 0, 1)
            ax.add_collection3d(Poly3DCollection(m.vertices[m.faces], facecolors=fc, linewidths=0))
        th = np.linspace(0, 2 * np.pi, 40)
        for z, r in zip(ZS[::25], RIN[::25]):
            ax.plot(r * np.cos(th), r * np.sin(th), z, color=(1, 0.6, 0.1), lw=0.6, alpha=0.6)
        ax.set_xlim(-17, 17); ax.set_ylim(-17, 17); ax.set_zlim(0, 46); ax.set_box_aspect((34, 34, 46))
        ax.view_init(el, az); ax.set_axis_off()
    fig.suptitle("3 parts packed in the closed Kinder capsule (orange: inner wall)")
    plt.tight_layout(); plt.savefig(os.path.join(HERE, "img", "g_packed.png"), dpi=110)
    return 0


if __name__ == "__main__":
    sys.exit(main())
