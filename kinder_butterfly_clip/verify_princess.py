"""CadQuery (OpenCascade) twin of the princess butterfly in rhino/kinder_rhino_build.py.
Uses the same pure-python geometry functions, then checks:
  - each part is one valid solid
  - assembly: right wing on top of the left wing, hooks through the slots, no interference
  - S-hook engagement under the left wing
  - packing of the 4 parts inside the real closed capsule shell (searches a packing, prints PACK)
Exports STEP/STL for preview and renders images."""
import math, os, sys, itertools
import cadquery as cq
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "rhino"))
import kinder_rhino_build as K

B, E = K.BF, K.EGG
OUT = os.path.join(HERE, "out")
T = B['T']


def wire(segs, wp):
    w = wp.moveTo(*segs[0][1])
    for s in segs:
        w = w.lineTo(*s[2]) if s[0] == 'L' else w.threePointArc(s[2], s[3])
    return w


def rev_partial(segs, c, a0, a1):
    s = wire(segs, cq.Workplane("XZ")).close().revolve(a1 - a0, (0, 0, 0), (0, 1, 0))
    return s.rotate((0, 0, 0), (0, 0, 1), a0).translate((c[0], c[1], 0))


def rev_full(segs, origin):
    return wire(segs, cq.Workplane("XZ")).close().revolve(360, (0, 0, 0), (0, 1, 0)).translate(origin)


def spline_closed(pts, z):
    return cq.Workplane("XY").workplane(offset=z).spline(pts, periodic=True).close()


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


def U(a, b):
    return a.union(b) if a is not None else b


def wing(side):
    mc = K.medallion_c(side)
    plate = spline_closed(K.wing_outline_pts(side), 0).extrude(T)
    try:
        plate = plate.faces(">Z").edges().fillet(B['EDGE_FILLET'])
    except Exception as ex:
        print("  plate fillet skipped:", ex)
    med = cq.Workplane().center(*mc).circle(B['MED_R']).extrude(T).faces(">Z").edges().fillet(B['EDGE_FILLET'])
    w = plate.union(med)
    zd = T + B['DECO_Z']
    for pts in K.border_pts(side):
        w = w.union(tube(pts, zd, B['BORDER_R']))
    for v in K.vein_pts(side):
        w = w.union(tube(v, zd, B['VEIN_R']))
    for (x, y, r) in K.pearl_pts(side):
        w = w.union(cq.Workplane().add(cq.Solid.makeSphere(r, cq.Vector(x, y, T - 0.12))))
    bh = B['BOSS_H'] + 0.2
    rt = B['BOSS_D'] / 2
    rb = rt - bh * math.tan(math.radians(B['BOSS_DRAFT']))
    for (x, y) in K.boss_pos(side):
        w = w.union(rev_full(K.pin_profile(rb, rt, bh), (x, y, -B['BOSS_H'])))
    cuts = [rev_full(K.hole_profile(B['CLIP_HOLE_D'] / 2, B['CLIP_HOLE_DEPTH']), (x, y, -B['BOSS_H']))
            for (x, y) in K.boss_pos(side)]
    R = B['MED_R']
    if side > 0:
        rs = (B['GEM_R'] ** 2 + B['GEM_H'] ** 2) / (2 * B['GEM_H'])
        sph = cq.Workplane().add(cq.Solid.makeSphere(rs, cq.Vector(mc[0], mc[1], T + B['GEM_H'] - rs)))
        w = w.union(sph.intersect(cq.Workplane().box(20, 20, 5, centered=(True, True, False))
                                  .translate((mc[0], mc[1], T - K.EPS))))
        w = w.union(cq.Workplane().add(cq.Solid.makeTorus(B['BEZEL_R'], B['BEZEL_PIPE'],
                                                          cq.Vector(mc[0], mc[1], zd), cq.Vector(0, 0, 1))))
        for i in range(B['BEAD_N']):
            a = 2 * math.pi * (i + 0.5) / B['BEAD_N']
            w = w.union(cq.Workplane().add(cq.Solid.makeSphere(
                B['BEAD_R'], cq.Vector(mc[0] + B['BEAD_RING'] * math.cos(a), mc[1] + B['BEAD_RING'] * math.sin(a), T - 0.05))))
        hooks, keys = K.hook_spans()
        for (a0, a1) in hooks:
            w = w.union(rev_partial(K.hook_profile(), mc, a0, a1))
            cuts.append(rev_partial(K.rect_profile(R - B['HOOK_T'] - B['RELIEF_W'], R - B['HOOK_T'], -0.5, B['RELIEF_D']),
                                    mc, a0 - 1, a1 + 1))
        for (a0, a1) in keys:
            w = w.union(rev_partial(K.rect_profile(R - B['SLOT_IN'] + 0.03, R - B['SLOT_IN'] + 0.63, -T, 0.3), mc, a0, a1))
    else:
        cuts.append(cq.Workplane("XY").workplane(offset=T - B['HEART_D'])
                    .spline(K.heart_pts(), periodic=True).close().extrude(B['HEART_D'] + 1))
        for (a0, a1) in K.slot_spans():
            cuts.append(rev_partial(K.rect_profile(R - B['SLOT_IN'], R + B['SLOT_OUT'], -1, T + 1),
                                    K.medallion_c(+1), a0, a1))
    for c in cuts:
        w = w.cut(c)
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


def vol(s):
    try:
        return s.val().Volume() if s.solids().size() else 0.0
    except Exception:
        return 0.0


def info(n, s):
    v = s.val()
    bb = v.BoundingBox()
    print("%-8s valid=%s solids=%d vol=%.0f mm3 (%.2f g ABS)  bbox %.1f x %.1f x %.1f" %
          (n, v.isValid(), s.solids().size(), v.Volume(), v.Volume() * 1.05e-3, bb.xlen, bb.ylen, bb.zlen))


if __name__ == "__main__":
    print(K.check_princess())
    wr, wl, cl = wing(+1), wing(-1), clip()
    for n, s in (("wing_R", wr), ("wing_L", wl), ("clip", cl)):
        info(n, s)
        cq.exporters.export(s, os.path.join(OUT, "princess_%s.step" % n))
        cq.exporters.export(s, os.path.join(OUT, "princess_%s.stl" % n), tolerance=0.02, angularTolerance=0.1)
    # ---- assembly
    asm = {"wing_L": wl, "wing_R": wr.translate((0, 0, T)),
           "clip_L": clip_on_wing(cl, -1), "clip_R": clip_on_wing(cl, +1).translate((0, 0, T))}
    names = list(asm)
    for i in range(4):
        for j in range(i + 1, 4):
            v = vol(asm[names[i]].intersect(asm[names[j]]))
            if v > 1e-4 and not ("clip" in names[i] + names[j] and "wing" in names[i] + names[j]):
                print("  ASM CLASH", names[i], names[j], round(v, 4))
            elif v > 1e-4:
                print("  press fit %s/%s %.3f mm3 (pin interference, intended)" % (names[i], names[j], v))
    # S-hook engagement: lip overlaps the left wing underside in plan, and does not touch it
    mc = K.medallion_c(+1)
    lip_band = (cq.Workplane().center(*mc).circle(B['MED_R'] + B['LIP']).circle(B['MED_R'] + B['SLOT_OUT'])
                .extrude(0.2))
    print("left wing material directly above the lips (engagement band area x0.2mm): %.3f mm3"
          % vol(wl.intersect(lip_band)))
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

    def place(s, rx, rz, d):
        return s.rotate((0, 0, 0), (1, 0, 0), rx).rotate((0, 0, 0), (0, 0, 1), rz).translate(d)

    def centre(s, rx, rz):
        bb = place(s, rx, rz, (0, 0, 0)).val().BoundingBox()
        return (-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, zc - (bb.zmin + bb.zmax) / 2), bb.ylen

    parts = {"R": wr, "L": wl, "C": cl}
    g = 0.4
    best = None
    # wings side by side in the middle, clips outside; try facing directions of the wings
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
        outside = sum(p.val().Volume() - vol(p.intersect(env)) for p in placed)
        mutual = sum(vol(placed[i].intersect(placed[j])) for i in range(4) for j in range(i + 1, 4))
        dmin = min(p.val().distance(shell.val()) for p in placed) if clash < 1e-6 else 0
        print("pack rxR=%d rxL=%d: shell clash %.3f, outside %.3f, mutual %.3f, min clearance %.2f"
              % (rxR, rxL, clash, outside, mutual, dmin))
        if clash < 1e-6 and outside < 1e-6 and mutual < 1e-6 and (best is None or dmin > best[0]):
            best = (dmin, cand, placed)
    if best:
        print("PACKING OK, min clearance %.2f mm" % best[0])
        print("PACK = [" + ",\n        ".join('("%s", (%g, %g, %.3f, %.3f, %.3f))' % ((k,) + tuple(tr)) for k, tr in best[1]) + "]")
        for (k, _), p in zip(best[1], best[2]):
            pass
        for i, p in enumerate(best[2]):
            cq.exporters.export(p, os.path.join(OUT, "ppack_%d.stl" % i), tolerance=0.03)
    else:
        print("PACKING FAIL")
