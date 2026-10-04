"""Preview images of the princess butterfly v3 (from verify_princess.py STL output)."""
import os, numpy as np, trimesh, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from render import draw, OUT, IMG
sys.path.insert(0, "rhino")
import kinder_rhino_build as K
L = lambda n: trimesh.load(os.path.join(OUT, n + ".stl"))
LIL, ROSE, WHITE, ORANGE = (0.80, 0.62, 0.95), (0.96, 0.55, 0.78), (0.95, 0.95, 0.97), (1.0, 0.62, 0.12)
a = {n: L("pasm_" + n) for n in ("wing_L", "wing_R", "clip_L", "clip_R")}
cols = {"wing_L": LIL, "wing_R": ROSE, "clip_L": WHITE, "clip_R": WHITE}
items = [(a[n], cols[n], 1) for n in a]
mv = lambda n, d: a[n].copy().apply_translation(d)


def top2d(ax, items, title, below=False):
    """orthographic top (or bottom) view, faces depth-sorted (painter), simple shading"""
    from matplotlib.collections import PolyCollection
    light = np.array([-0.4, 0.5, 0.75]); light /= np.linalg.norm(light)
    polys, cols_, depth = [], [], []
    for m, col, _ in items:
        n = m.face_normals
        keep = (n[:, 2] < -0.02) if below else (n[:, 2] > 0.02)
        tri = m.vertices[m.faces[keep]]
        sh = 0.55 + 0.45 * np.clip((n[keep] * ([1, 1, -1] if below else 1)) @ light, 0, 1)
        polys.append(tri[:, :, :2] * ([-1, 1] if below else 1))
        cols_.append(np.clip(np.array(col)[None] * sh[:, None], 0, 1))
        depth.append(tri[:, :, 2].mean(1) * (-1 if below else 1))
    P, C, D = np.concatenate(polys), np.concatenate(cols_), np.concatenate(depth)
    o = np.argsort(D)
    ax.add_collection(PolyCollection(P[o], facecolors=C[o], edgecolors=C[o], linewidths=0.2))
    ax.autoscale(); ax.set_aspect("equal"); ax.axis("off"); ax.set_title(title, fontsize=10)

fig = plt.figure(figsize=(18, 11))
top2d(fig.add_subplot(231), items, "Assembled - top view (3 hearts + jewel = the 'body')")
draw(fig.add_subplot(232, projection="3d"), items, 30, -62, "Assembled - 3/4 view")
top2d(fig.add_subplot(233), items, "Underside (mirrored): female band, tabs, 2 clips", below=True)
ins = [(mv("wing_L", (0, 0, 0)), LIL, 1), (mv("clip_L", (0, 0, 0)), WHITE, 1),
       (mv("wing_R", (9, 0, 0)), ROSE, 1), (mv("clip_R", (9, 0, 0)), WHITE, 1)]
draw(fig.add_subplot(234, projection="3d"), ins, 38, -55, "Assembly: slide the right tongue in under the left wing")
# joint section through the jewel
ax = fig.add_subplot(235)
gy = K.gem_centre()[1]
for nm, c in (("wing_L", "#9b6bd6"), ("wing_R", "#e0559a")):
    for p, q in trimesh.intersections.mesh_plane(a[nm], plane_normal=(0, 1, 0), plane_origin=(0, gy, 0)):
        ax.plot([p[0], q[0]], [p[2], q[2]], color=c, lw=1.4)
ax.set_xlim(-7, 6); ax.set_ylim(-2.0, 3.0); ax.set_aspect("equal"); ax.grid(alpha=.3)
ax.set_xlabel("x (mm)"); ax.set_ylabel("z (mm)")
ax.set_title("Joint section through the jewel\npurple = left wing (female)   pink = right wing (male tongue)")
pk = [(L("ppack_%d" % i), c, 1) for i, c in enumerate((ROSE, LIL, WHITE, WHITE))]
for s in ("base_hinge", "cap"):
    m = L("egg_Egg_Closed_" + s)
    pk.append((m.slice_plane((0, 0, 0), (0, 1, 0), cap=True), ORANGE, 1))
draw(fig.add_subplot(236, projection="3d"), pk, 10, -80, "Packed in the closed egg (section)", lim=26)
plt.tight_layout(); plt.savefig(os.path.join(IMG, "princess_overview.png"), dpi=100)

# separated: two hair clips for two friends
fig = plt.figure(figsize=(12, 5))
sep = [(mv("wing_R", (8, 0, 0)), ROSE, 1), (mv("clip_R", (8, 0, 0)), WHITE, 1),
       (mv("wing_L", (-8, 0, 0)), LIL, 1), (mv("clip_L", (-8, 0, 0)), WHITE, 1)]
top2d(fig.add_subplot(121), sep, "Separated: two hair clips (top)")
draw(fig.add_subplot(122, projection="3d"), sep, 35, -75, "Separated (3/4)")
plt.tight_layout(); plt.savefig(os.path.join(IMG, "princess_separated.png"), dpi=100)
print("ok")
