"""Check the pure-maths part of rhino/kinder_rhino_build.py outside Rhino, by building the same
geometry with CadQuery (OpenCascade). Also exports the egg in 3 states (STEP) and checks that the
packed toy fits inside the real capsule shell."""
import math, os, sys
import cadquery as cq
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "rhino"))
import kinder_rhino_build as K
import build as B
import pack as PK

OUT = B.OUT
E = K.EGG


def wire(segs, wp):
    w = wp.moveTo(*segs[0][1])
    for s in segs:
        w = w.lineTo(*s[2]) if s[0] == 'L' else w.threePointArc(s[2], s[3])
    return w


def revolve(segs):
    return wire(segs, cq.Workplane("XZ")).close().revolve(360, (0, 0, 0), (0, 1, 0))


# 1. continuity of every profile
for name, segs, closed in [("base outer", K.egg_base_outer(), False), ("base inner", K.egg_base_inner(), False),
                           ("cap outer", K.egg_cap_outer(), False), ("cap inner", K.egg_cap_inner(), False),
                           ("snap rib", K.egg_snap_rib(), True), ("strap 0", K.hinge_strap(0), True),
                           ("strap 90", K.hinge_strap(90), True), ("strap 180", K.hinge_strap(180), True),
                           ("clip", K.clip_outline(), True)]:
    ok = K.check_chain(segs, closed)
    ends = (segs[0][1], segs[-1][-1])
    print("%-11s continuous=%s  start=%s end=%s" % (name, ok, tuple(round(v, 3) for v in ends[0]),
                                                    tuple(round(v, 3) for v in ends[1])))
    assert ok

# 2. egg halves
base = revolve(K.egg_base_outer()).cut(revolve(K.egg_base_inner()))
zr = E['Z_SEAM'] + E['SNAP_DZ']
tor = cq.Solid.makeTorus(E['NECK_R'] + E['GROOVE_R'] - E['GROOVE_DEPTH'], E['GROOVE_R'],
                         cq.Vector(0, 0, zr), cq.Vector(0, 0, 1))
base = base.cut(cq.Workplane().add(tor))
cap = revolve(K.egg_cap_outer()).cut(revolve(K.egg_cap_inner()))
cap = cap.union(wire(K.egg_snap_rib(), cq.Workplane("XZ")).close().revolve(360, (0, 0, 0), (0, 1, 0)))
pb, pc, pad_b, pad_c = K.hinge_attach()
w = E['H_W']


def bx(x0, x1, z0, z1):
    return cq.Workplane().box(x1 - x0, w, z1 - z0).translate(((x0 + x1) / 2, 0, (z0 + z1) / 2))


base = base.union(bx(*pad_b))
cap = cap.union(bx(*pad_c))
for n, s in (("base", base), ("cap", cap)):
    v = s.val()
    bb = v.BoundingBox()
    print("%s valid=%s solids=%d vol=%.0f mm3  z[%.2f, %.2f] rmax=%.2f" %
          (n, v.isValid(), len(s.solids().vals()), v.Volume(), bb.zmin, bb.zmax, bb.xmax))
print("closed length = %.2f (drawing 45.32)" % (cap.val().BoundingBox().zmax - base.val().BoundingBox().zmin))
print("wall at base bottom = %.2f, cap top = %.2f" % (E['T'], E['T']))
ov = base.intersect(cap).val().Volume()
print("closed-state base/cap overlap (snap interference) = %.3f mm3" % ov)

hx, hz = K.hinge_pivot()
states = {}
for name, th in E['STATES']:
    strap = wire(K.hinge_strap(th), cq.Workplane("XZ", origin=(0, w / 2, 0))).close().extrude(w)
    cap_t = cap.rotate((hx, 0, hz), (hx, -1, hz), th)
    if th > 0:
        clash = base.intersect(cap_t).val().Volume()
        egg = base.union(strap).union(cap_t)
        print("%-13s cap/base clash=%.3f  solids=%d valid=%s" % (name, clash, len(egg.solids().vals()), egg.val().isValid()))
        states[name] = [("shell", egg)]
    else:
        bh = base.union(strap)
        print("%-13s base+hinge solids=%d valid=%s" % (name, len(bh.solids().vals()), bh.val().isValid()))
        states[name] = [("base+hinge", bh), ("cap", cap_t)]
    a = cq.Assembly()
    for sub, s in states[name]:
        a.add(s, name=sub, color=cq.Color(1.0, 0.62, 0.12))
    a.save(os.path.join(OUT, "egg_%s.step" % name))
    for sub, s in states[name]:
        cq.exporters.export(s, os.path.join(OUT, "egg_%s_%s.stl" % (name, sub.replace("+", "_"))), tolerance=0.03)

# 3. clip from the Rhino outline vs CadQuery build.py clip
clip = wire(K.clip_outline(), cq.Workplane("YZ")).close().extrude(B.CLIP_W)
for y in (4.0, 20.0):
    clip = clip.union(cq.Workplane().add(cq.Solid.makeCylinder(B.CLIP_PIN_D / 2, B.CLIP_PIN_H, cq.Vector(B.CLIP_W / 2, y, 0))))
print("clip (Rhino outline) valid=%s vol=%.0f  | build.py clip vol=%.0f" %
      (clip.val().isValid(), clip.val().Volume(), B.clip().val().Volume()))

# 4. packed toy inside the real closed shell
wr, wl, cl = B.wing_R(), B.wing_L(), B.clip()
W = lambda s: PK.centre_xy_z(s.rotate((0, 0, 0), (1, 0, 0), 90))
wrp, wlp, cp = W(wr), W(wl), W(cl)
th = lambda s: s.val().BoundingBox().ylen
g = 0.3
zc = E['L_TOTAL'] / 2
packed = {"wing_R": wrp.translate((0, -(th(wrp) / 2 + g / 2), zc)),
          "wing_L": wlp.translate((0, th(wlp) / 2 + g / 2, zc)),
          "clip_1": cp.translate((0, th(wlp) + g + th(cp) / 2 + g, zc)),
          "clip_2": cp.rotate((0, 0, 0), (0, 0, 1), 180).translate((0, -(th(wrp) + g + th(cp) / 2 + g), zc))}
envelope = revolve(K.egg_base_outer()).union(revolve(K.egg_cap_outer()))
shell = states["Egg_Closed"][0][1].union(states["Egg_Closed"][1][1])
ok = True
for n, s in packed.items():
    hit = s.intersect(shell).val().Volume() if s.intersect(shell).solids().size() else 0.0
    inside = s.intersect(envelope).val().Volume() / s.val().Volume()
    # minimum clearance to the shell
    d = s.val().distance(shell.val())
    print("packed %-7s shell overlap=%.4f  inside=%.4f  clearance=%.2f mm" % (n, hit, inside, d))
    ok &= hit < 1e-6 and inside > 0.9999
    cq.exporters.export(s, os.path.join(OUT, "packedegg_%s.stl" % n), tolerance=0.03)
names = list(packed)
for i in range(4):
    for j in range(i + 1, 4):
        ok &= packed[names[i]].intersect(packed[names[j]]).solids().size() == 0
print("PACKED IN REAL SHELL:", "OK" if ok else "FAIL")
