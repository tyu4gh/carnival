"""Preview images of the princess butterfly (from verify_princess.py STL output)."""
import os, math, numpy as np, trimesh, sys
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

fig = plt.figure(figsize=(16, 11))
draw(fig.add_subplot(231, projection="3d"), items, 62, -90, "Assembled - top")
draw(fig.add_subplot(232, projection="3d"), items, 28, -60, "Assembled - 3/4 view")
draw(fig.add_subplot(233, projection="3d"), items, -40, -70, "Underside: 2 clips, 2 S-hooks")
T = K.BF['T']
sep = [(a["wing_R"].copy().apply_translation((14, 0, 0)), ROSE, 1),
       (a["clip_R"].copy().apply_translation((14, 0, 0)), WHITE, 1),
       (a["wing_L"].copy().apply_translation((-14, 0, 0)), LIL, 1),
       (a["clip_L"].copy().apply_translation((-14, 0, 0)), WHITE, 1)]
draw(fig.add_subplot(234, projection="3d"), sep, 55, -90, "Separated: two hair clips")
# S-hook section through hook centre (130 deg around the right medallion centre)
ax = fig.add_subplot(235)
mc = K.medallion_c(+1)
ang = math.radians(K.BF['HOOK_ANG'][0])
d = np.array([math.cos(ang), math.sin(ang), 0])
n = np.array([-d[1], d[0], 0])
for nm, c in (("wing_L", "#9b6bd6"), ("wing_R", "#e0559a")):
    segs = trimesh.intersections.mesh_plane(a[nm], plane_normal=n, plane_origin=(mc[0], mc[1], 0))
    for p, q in segs:
        rp = (p[:2] - mc) @ d[:2]; rq = (q[:2] - mc) @ d[:2]
        ax.plot([rp, rq], [p[2], q[2]], color=c, lw=1.4)
ax.set_xlim(2.0, 7.5); ax.set_ylim(-2.0, 5.0); ax.set_aspect("equal"); ax.grid(alpha=.3)
ax.set_xlabel("radius from jewel centre (mm)"); ax.set_ylabel("z (mm)")
ax.set_title("S-hook section (pink = top wing R, purple = bottom wing L)")
pk = [(L("ppack_%d" % i), c, 1) for i, c in enumerate((ROSE, LIL, WHITE, WHITE))]
for s in ("base_hinge", "cap"):
    m = L("egg_Egg_Closed_" + s)
    pk.append((m.slice_plane((0, 0, 0), (0, 1, 0), cap=True), ORANGE, 1))
draw(fig.add_subplot(236, projection="3d"), pk, 10, -80, "Packed in the closed egg (section)", lim=26)
plt.tight_layout(); plt.savefig(os.path.join(IMG, "princess_overview.png"), dpi=100)
print("ok")
