"""Preview images + Rhino .3dm (meshes on layers). STEP files hold the NURBS solids."""
import os, numpy as np, trimesh, rhino3dm
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")
os.makedirs(IMG, exist_ok=True)
L = lambda n: trimesh.load(os.path.join(OUT, n + ".stl"))
PINK, WHITE, GLASS = (0.96, 0.48, 0.72), (0.93, 0.93, 0.96), (1.0, 0.75, 0.2)


def draw(ax, items, elev, azim, title, lim=None):
    light = np.array([0.3, -0.5, 0.8]); light /= np.linalg.norm(light)
    for m, col, alpha in items:
        tri = m.vertices[m.faces]
        sh = 0.45 + 0.55 * np.clip(m.face_normals @ light, 0, 1)
        fc = np.clip(np.array(col)[None, :] * sh[:, None], 0, 1)
        pc = Poly3DCollection(tri, facecolors=np.c_[fc, np.full(len(fc), alpha)], linewidths=0)
        ax.add_collection3d(pc)
    allv = np.vstack([m.vertices for m, _, _ in items])
    c = (allv.max(0) + allv.min(0)) / 2; r = lim or (allv.max(0) - allv.min(0)).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(elev, azim); ax.set_axis_off(); ax.set_title(title, fontsize=10)


if __name__ == "__main__":
    asm = {n: L("asm_" + n) for n in ("wing_R", "wing_L", "clip_R", "clip_L")}
    fig = plt.figure(figsize=(14, 10))
    draw(fig.add_subplot(221, projection="3d"),
         [(asm["wing_R"], PINK, 1), (asm["wing_L"], PINK, 1), (asm["clip_R"], WHITE, 1), (asm["clip_L"], WHITE, 1)],
         35, -60, "Assembled butterfly (top)")
    draw(fig.add_subplot(222, projection="3d"),
         [(asm["wing_R"], PINK, 1), (asm["wing_L"], PINK, 1), (asm["clip_R"], WHITE, 1), (asm["clip_L"], WHITE, 1)],
         -35, -60, "Assembled (underside: 2 clips)")
    ex = lambda m, d: m.copy().apply_translation(d)
    draw(fig.add_subplot(223, projection="3d"),
         [(ex(asm["wing_R"], (6, 0, 6)), PINK, 1), (ex(asm["wing_L"], (-6, 0, 10)), PINK, 1),
          (ex(asm["clip_R"], (6, 0, -6)), WHITE, 1), (ex(asm["clip_L"], (-6, 0, -6)), WHITE, 1)],
         20, -70, "Exploded: P1 wing R, P2 wing L, P3 clip x2")
    pk = [(L("pack_wing_R"), PINK, 1), (L("pack_wing_L"), (0.85, 0.35, 0.6), 1),
          (L("pack_clip_1"), WHITE, 1), (L("pack_clip_2"), WHITE, 1),
          (L("capsule_inner_space"), GLASS, 0.12)]
    draw(fig.add_subplot(224, projection="3d"), pk, 15, -35, "Packed in capsule inner space (R15.3 x 42.4)")
    plt.tight_layout(); plt.savefig(os.path.join(IMG, "overview.png"), dpi=110)

    # clip side section
    import build as B
    m = L("P3_clip")
    segs = trimesh.intersections.mesh_plane(m, plane_normal=(1, 0, 0), plane_origin=(B.CLIP_W / 2 - 0.5, 0, 0))
    fig, ax = plt.subplots(figsize=(10, 4))
    for a, b in segs:
        ax.plot([a[1], b[1]], [a[2], b[2]], "k-", lw=1)
    ax.set_aspect("equal"); ax.grid(alpha=.3); ax.set_xlabel("Y mm"); ax.set_ylabel("Z mm")
    ax.set_title("P3 clip - side section (hair slides in from the left; press thumb tab down to open)")
    plt.tight_layout(); plt.savefig(os.path.join(IMG, "clip_section.png"), dpi=110)

    # Rhino 3dm: meshes on layers (assembly / exploded parts / egg packing)
    f = rhino3dm.File3dm(); f.Settings.ModelUnitSystem = rhino3dm.UnitSystem.Millimeters
    def layer(name, rgb):
        l = rhino3dm.Layer(); l.Name = name; l.Color = (*rgb, 255); return f.Layers.Add(l)
    def add(mesh, li, name, dx=(0, 0, 0)):
        rm = rhino3dm.Mesh()
        for v in mesh.vertices + np.array(dx): rm.Vertices.Add(*map(float, v))
        for a, b, c_ in mesh.faces: rm.Faces.AddFace(int(a), int(b), int(c_))
        rm.Normals.ComputeNormals(); rm.Compact()
        at = rhino3dm.ObjectAttributes(); at.LayerIndex = li; at.Name = name
        f.Objects.AddMesh(rm, at)
    la = layer("01_Assembly", (245, 120, 180))
    for n, msh in asm.items(): add(msh, la, n)
    lp = layer("02_Parts_flat", (120, 160, 245))
    add(L("P1_wing_R"), lp, "P1_wing_R", (60, 0, 0)); add(L("P2_wing_L"), lp, "P2_wing_L", (90, 0, 0))
    add(L("P3_clip"), lp, "P3_clip", (115, -12, 0))
    lk = layer("03_Packed_in_egg", (240, 200, 60))
    for n in ("wing_R", "wing_L", "clip_1", "clip_2"): add(L("pack_" + n), lk, "pack_" + n, (0, 70, 0))
    lc = layer("04_Capsule_inner_space_ref", (200, 200, 200))
    add(L("capsule_inner_space"), lc, "capsule_inner", (0, 70, 0))
    f.Write(os.path.join(OUT, "kinder_butterfly_clip.3dm"), 7)
    print("done")
