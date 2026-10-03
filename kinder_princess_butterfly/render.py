"""Preview images from the STL files written by verify.py."""
import os, sys, numpy as np, trimesh
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
HERE = os.path.dirname(os.path.abspath(__file__))
OUT, IMG = os.path.join(HERE, "out"), os.path.join(HERE, "img")
L = lambda n: trimesh.load(os.path.join(OUT, n + ".stl"))
PINK, LILAC, WHITE, ORANGE = (0.97, 0.62, 0.80), (0.80, 0.68, 0.95), (0.95, 0.95, 0.98), (1.0, 0.62, 0.12)


def draw(ax, items, elev, azim, title, lim=None, ortho=False):
    light = np.array([0.25, -0.45, 0.85]); light /= np.linalg.norm(light)
    for m, col, alpha in items:
        tri = m.vertices[m.faces]
        sh = 0.5 + 0.5 * np.clip(m.face_normals @ light, 0, 1)
        fc = np.clip(np.array(col)[None, :] * sh[:, None], 0, 1)
        ax.add_collection3d(Poly3DCollection(tri, facecolors=np.c_[fc, np.full(len(fc), alpha)], linewidths=0))
    v = np.vstack([m.vertices for m, _, _ in items])
    c = (v.max(0) + v.min(0)) / 2; r = lim or (v.max(0) - v.min(0)).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(elev, azim); ax.set_axis_off(); ax.set_title(title, fontsize=11)
    if ortho:
        ax.set_proj_type("ortho")


R, Lw, cR, cL = L("asm_wing_R"), L("asm_wing_L"), L("asm_clip_R"), L("asm_clip_L")
fig = plt.figure(figsize=(16, 11))
draw(fig.add_subplot(231, projection="3d"), [(R, PINK, 1), (Lw, LILAC, 1)], 90, -90,
     "Top view (UV relief: frames, veins, pearls)", ortho=True)
draw(fig.add_subplot(232, projection="3d"), [(R, PINK, 1), (Lw, LILAC, 1), (cR, WHITE, 1), (cL, WHITE, 1)],
     30, -65, "Assembled hair clip")
draw(fig.add_subplot(233, projection="3d"), [(R, PINK, 1), (Lw, LILAC, 1), (cR, WHITE, 1), (cL, WHITE, 1)],
     -40, -65, "Underside: one clip per wing")
mv = lambda m, d: m.copy().apply_translation(d)
draw(fig.add_subplot(234, projection="3d"),
     [(R, PINK, 1), (mv(Lw, (-3, 0, 9)), LILAC, 1), (mv(cR, (0, 0, -9)), WHITE, 1), (mv(cL, (0, 0, -9)), WHITE, 1)],
     22, -70, "Exploded: press L onto R, clips into bosses")
# joint section y = 0 (sketch "WING CONNECT")
ax = fig.add_subplot(235)
for m, col in ((R, PINK), (Lw, LILAC)):
    segs = trimesh.intersections.mesh_plane(m, plane_normal=(0, 1, 0), plane_origin=(0, 0.01, 0))
    for p0, p1 in segs:
        ax.plot([p0[0], p1[0]], [p0[2], p1[2]], color=("crimson" if col == PINK else "indigo"), lw=1.6)
ax.set_xlim(-9, 9); ax.set_ylim(-1.8, 3); ax.set_aspect("equal"); ax.grid(alpha=.3)
ax.set_title("Joint section at centre (red = wing R, blue = wing L)", fontsize=11)
ax.set_xlabel("X mm"); ax.set_ylabel("Z mm")
items = [(L("egg_base").slice_plane((0, 0, 0), (0, 1, 0), cap=True), ORANGE, 1),
         (L("egg_cap").slice_plane((0, 0, 0), (0, 1, 0), cap=True), ORANGE, 1)]
items += [(L("packed_" + n), c, 1) for n, c in (("wing_R", PINK), ("wing_L", LILAC), ("clip_1", WHITE), ("clip_2", WHITE))]
draw(fig.add_subplot(236, projection="3d"), items, 8, -80, "Packed in the Kinder capsule (section)", lim=26)
plt.tight_layout(); plt.savefig(os.path.join(IMG, "overview.png"), dpi=100)

fig = plt.figure(figsize=(12, 6))
draw(fig.add_subplot(121, projection="3d"), [(L("P1_wing_R"), PINK, 1), (cR, WHITE, 1)], 35, -60,
     "Wing R alone = hair clip for a friend")
draw(fig.add_subplot(122, projection="3d"), [(L("P2_wing_L"), LILAC, 1), (cL.copy().apply_translation((0, 0, 0)), WHITE, 1)],
     35, -120, "Wing L alone = second hair clip")
plt.tight_layout(); plt.savefig(os.path.join(IMG, "single_wings.png"), dpi=100)
print("ok")
