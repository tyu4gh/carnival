"""CadQuery (OpenCascade) twin of the princess butterfly v3 in rhino/kinder_rhino_build.py.
Uses the same pure-python geometry functions (outline, offsets, hearts, decoration), then checks:
  - each part is one valid solid
  - assembly: no interference between the wings (clip pins = intended press fit)
  - interlock: moving the right wing up / down / left / right collides with the left wing
  - packing of the 4 parts inside the real closed capsule shell (prints PACK for the Rhino script)
Exports STEP/STL for preview."""
import math, os, sys, itertools
import cadquery as cq
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "rhino"))
import kinder_rhino_build as K

B, E = K.BF, K.EGG
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
T = B['T']


def wire(segs, wp):
    w = wp.moveTo(*segs[0][1])
    for s in segs:
        w = w.lineTo(*s[2]) if s[0] == 'L' else w.threePointArc(s[2], s[3])
    return w


def rev_full(segs, origin):
    return wire(segs, cq.Workplane("XZ")).close().revolve(360, (0, 0, 0), (0, 1, 0)).translate(origin)


def prism(pts, z0, z1):
    return cq.Workplane("XY").workplane(offset=z0).spline(pts, periodic=True).close().extrude(z1 - z0)


def band_prism(z0, z1):
    arc, box_pts = K.band_outline()
    w = cq.Workplane("XY").workplane(offset=z0).moveTo(*arc[0]).spline(arc[1:], includeCurrent=True)
    for p in box_pts[1:-1]:
        w = w.lineTo(*p)
    return w.close().extrude(z1 - z0)


def tube(pts, z, r):
    """swept circle along an open spline + round end caps"""
    path = cq.Workplane("XY").spline([(x, y, z) for (x, y) in pts], includeCurrent=False)
    e = path.val()
    t0 = e.tangentAt(0)
    prof = cq.Workplane(cq.Plane(origin=e.startPoint(), xDir=cq.Vector(0, 0, 1).cross(t0), normal=t0)).circle(r)
    s = prof.sweep(path, transition="round")
    for p in (e.startPoint(), e.endPoint()):
        s = s.union(cq.Workplane().add(cq.Solid.makeSphere(r, p)))
    return s


def vol(s):
    try:
        return sum(v.Volume() for v in s.solids().vals())
    except Exception:
        return 0.0


def wing(side):
    own, other = K.wing_outline_pts(side), K.wing_outline_pts(-side)
    plate = prism(own, 0, T)
    plate = plate.faces(">Z").edges().fillet(B['FILLET_TOP'])
    plate = plate.faces("<Z").edges().fillet(B['FILLET_BOT'])
    w = plate
    for run in K.border_runs(side):
        w = w.union(tube(run, T, B['DECO_R']))
    for v in K.vein_pts(side):
        w = w.union(tube(v, T, B['DECO_R']))
    for (x, y, r) in K.pearl_pts(side):
        w = w.union(cq.Workplane().add(cq.Solid.makeSphere(r, cq.Vector(x, y, T - 0.1))))
    bh = B['BOSS_H'] + 0.2
    rt = B['BOSS_D'] / 2
    rb = rt - bh * math.tan(math.radians(B['BOSS_DRAFT']))
    for (x, y) in K.boss_pos(side):
        w = w.union(rev_full(K.pin_profile(rb, rt, bh), (x, y, -B['BOSS_H'])))
    cuts = [rev_full(K.hole_profile(B['CLIP_HOLE_D'] / 2, B['CLIP_HOLE_DEPTH']), (x, y, -B['BOSS_H']))
            for (x, y) in K.boss_pos(side)]
    if side < 0:
        band = band_prism(B['THICK_Z0'], 0.5).intersect(
            prism(K.offset_closed(own, B['THICK_INSET']), B['THICK_Z0'] - 1, 1.0))
        w = w.union(band)
        cuts.append(prism(K.offset_closed(other, -B['CLR']), B['THICK_Z0'] - 0.3, B['LIP_Z0']))
        for c in cuts:
            w = w.cut(c)
        hearts = K.heart_windows()
        for (p, r) in K.tab_discs():
            w = w.union(cq.Workplane().add(cq.Solid.makeCylinder(r, 0.5 - B['TAB_Z0'], cq.Vector(p[0], p[1], B['TAB_Z0']))))
        for (c, wd, tab) in hearts:
            w = w.cut(prism(K.heart_pts(c, wd), B['FLOOR_Z'], T + 1))
    else:
        cuts.append(prism(K.offset_closed(other, -B['CLR']), B['TONGUE_T'], T + 1))
        for c in cuts:
            w = w.cut(c)
        g, r0, r1 = K.gem()
        w = w.union(rev_full(K.pin_profile(r0 + K.EPS, r1, B['GEM_H'] + K.EPS),
                             (g[0], g[1], B['TONGUE_T'] - K.EPS)))
    return w


def clip():
    c = wire(K.clip_outline(), cq.Workplane("YZ")).close().extrude(B['CLIP_W'])
    for y in B['CLIP_PIN_Y']:
        c = c.union(rev_full(K.pin_profile(B['CLIP_PIN_D'] / 2, B['CLIP_PIN_D'] / 2, B['CLIP_PIN_H'] + 0.1, 0.35),
                             (B['CLIP_W'] / 2, y, -0.1)))
    return c


def clip_on_wing(c, side):
    x, y = K.boss_pos(side)[0]
    return c.translate((x - B['CLIP_W'] / 2, y - B['CLIP_PIN_Y'][0], -B['BOSS_H']))


def info(n, s):
    v = s.val()
    bb = v.BoundingBox()
    print("%-8s valid=%s solids=%d vol=%.0f mm3 (%.2f g ABS)  bbox %.1f x %.1f x %.1f" %
          (n, v.isValid(), s.solids().size(), vol(s), vol(s) * 1.05e-3, bb.xlen, bb.ylen, bb.zlen))


if __name__ == "__main__":
    for k, v in K.check_princess().items():
        print(("OK   " if v[0] else "FAIL ") + k, v[1])
    wr, wl, cl = wing(+1), wing(-1), clip()
    for n, s in (("wing_R", wr), ("wing_L", wl), ("clip", cl)):
        info(n, s)
        cq.exporters.export(s, os.path.join(OUT, "princess_%s.step" % n))
        cq.exporters.export(s, os.path.join(OUT, "princess_%s.stl" % n), tolerance=0.02, angularTolerance=0.1)
    # ---- assembly
    asm = {"wing_L": wl, "wing_R": wr, "clip_L": clip_on_wing(cl, -1), "clip_R": clip_on_wing(cl, +1)}
    names = list(asm)
    for i in range(4):
        for j in range(i + 1, 4):
            v = vol(asm[names[i]].intersect(asm[names[j]]))
            pair = names[i] + "/" + names[j]
            if v > 1e-4 and not ("clip" in pair and "wing" in pair):
                print("  ASM CLASH", pair, round(v, 4))
            elif v > 1e-4:
                print("  press fit %s %.3f mm3 (pin interference, intended)" % (pair, v))
    print("wing_R / wing_L interference: %.4f mm3" % vol(wr.intersect(wl)))
    # ---- interlock: every escape direction of the right wing must hit the left wing
    for name, d in (("up 0.3", (0, 0, 0.3)), ("down 0.3", (0, 0, -0.3)),
                    ("out to the right 0.6", (0.6, 0, 0)), ("in to the left 0.6", (-0.6, 0, 0)),
                    ("forward 0.6", (0, 0.6, 0)), ("back 0.6", (0, -0.6, 0))):
        v = vol(wr.translate(d).intersect(wl))
        print("  interlock: right wing moved %-22s -> collision %.3f mm3 %s" % (name, v, "BLOCKED" if v > 1e-3 else "free"))
    a = cq.Assembly()
    cols = {"wing_L": (0.80, 0.62, 0.95), "wing_R": (0.96, 0.55, 0.78), "clip_L": (1, 1, 1), "clip_R": (1, 1, 1)}
    for n, s in asm.items():
        a.add(s, name=n, color=cq.Color(*cols[n]))
        cq.exporters.export(s, os.path.join(OUT, "pasm_%s.stl" % n), tolerance=0.02, angularTolerance=0.1)
    a.save(os.path.join(OUT, "princess_assembly.step"))

    # ---- packing inside the real closed capsule
    def rev(segs):
        return wire(segs, cq.Workplane("XZ")).close().revolve(360, (0, 0, 0), (0, 1, 0))
    base = rev(K.egg_base_outer()).cut(rev(K.egg_base_inner()))
    cap = rev(K.egg_cap_outer()).cut(rev(K.egg_cap_inner()))
    shell = base.union(cap)
    env = rev(K.egg_base_outer()).union(rev(K.egg_cap_outer()))
    zc = E['L_TOTAL'] / 2
    for nm, s in (("base_hinge", base), ("cap", cap)):
        cq.exporters.export(s, os.path.join(OUT, "egg_Egg_Closed_%s.stl" % nm), tolerance=0.03)

    def place(s, rx, rz, d):
        return s.rotate((0, 0, 0), (1, 0, 0), rx).rotate((0, 0, 0), (0, 0, 1), rz).translate(d)

    def centre(s, rx, rz):
        bb = place(s, rx, rz, (0, 0, 0)).val().BoundingBox()
        return (-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, zc - (bb.zmin + bb.zmax) / 2), bb.ylen

    parts = {"R": wr, "L": wl, "C": cl}
    g = 0.4
    best = None
    for rxR, rxL in itertools.product((90, -90), (90, -90)):
        dR, tR = centre(wr, rxR, 0)
        dL, tL = centre(wl, rxL, 0)
        dC, tC = centre(cl, 90, 0)
        y0 = -(tR + tL + g) / 2
        cand = [("R", (rxR, 0, dR[0], dR[1] + y0 + tR / 2, dR[2])),
                ("L", (rxL, 0, dL[0], dL[1] + y0 + tR + g + tL / 2, dL[2])),
                ("C", (90, 0, dC[0], dC[1] + y0 + tR + g + tL + g + tC / 2, dC[2])),
                ("C", (90, 180, -dC[0], -dC[1] + y0 - g - tC / 2, dC[2]))]
        placed = [place(parts[k], tr[0], tr[1], tr[2:]) for k, tr in cand]
        clash = sum(vol(p.intersect(shell)) for p in placed)
        outside = sum(vol(p) - vol(p.intersect(env)) for p in placed)
        mutual = sum(vol(placed[i].intersect(placed[j])) for i in range(4) for j in range(i + 1, 4))
        dmin = min(p.val().distance(shell.val()) for p in placed) if clash < 1e-6 else 0
        print("pack rxR=%d rxL=%d: shell clash %.3f, outside %.3f, mutual %.3f, min clearance %.2f"
              % (rxR, rxL, clash, outside, mutual, dmin))
        if clash < 1e-6 and outside < 1e-6 and mutual < 1e-6 and (best is None or dmin > best[0]):
            best = (dmin, cand, placed)
    if best:
        print("PACKING OK, min clearance %.2f mm" % best[0])
        print("PACK = [" + ",\n        ".join('("%s", (%g, %g, %.3f, %.3f, %.3f))' % ((k,) + tuple(tr)) for k, tr in best[1]) + "]")
        for i, p in enumerate(best[2]):
            cq.exporters.export(p, os.path.join(OUT, "ppack_%d.stl" % i), tolerance=0.03)
    else:
        print("PACKING FAIL")
