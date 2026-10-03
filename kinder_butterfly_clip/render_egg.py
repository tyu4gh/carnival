"""Preview of the capsule in 3 states + closed section with the packed toy."""
import os, numpy as np, trimesh
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from render import draw, OUT, IMG
ORANGE, PINK, WHITE = (1.0, 0.62, 0.12), (0.96, 0.48, 0.72), (0.93, 0.93, 0.96)
L = lambda n: trimesh.load(os.path.join(OUT, n + ".stl"))
fig = plt.figure(figsize=(16, 5.5))
for k, (st, subs, title) in enumerate([("Egg_Closed", ["base_hinge", "cap"], "Closed (0 deg)"),
                                       ("Egg_HalfOpen", ["shell"], "Half open (90 deg)"),
                                       ("Egg_Open", ["shell"], "Open / as moulded (180 deg)")]):
    ms = [(L("egg_%s_%s" % (st, s)), ORANGE, 1) for s in subs]
    draw(fig.add_subplot(1, 4, k + 1, projection="3d"), ms, 12, -110, title, lim=28)
# section: cut the closed shell at y > 0 and show packed parts
ax = fig.add_subplot(1, 4, 4, projection="3d")
items = []
for s in ("base_hinge", "cap"):
    m = L("egg_Egg_Closed_" + s)
    items.append((m.slice_plane((0, 0, 0), (0, 1, 0), cap=True), ORANGE, 1))
for n, c in (("wing_R", PINK), ("wing_L", (0.85, 0.35, 0.6)), ("clip_1", WHITE), ("clip_2", WHITE)):
    items.append((L("packedegg_" + n), c, 1))
draw(ax, items, 10, -80, "Closed, section + packed toy", lim=26)
plt.tight_layout(); plt.savefig(os.path.join(IMG, "egg_states.png"), dpi=105)
print("ok")
