"""Rebuild the princess butterfly with CadQuery (OpenCascade) from the SAME maths as
rhino/princess_butterfly_rhino.py, then check validity, the interlock, the UV relief,
and packing inside the real Kinder capsule. Exports STEP + STL + preview images."""
import math, os, sys
import cadquery as cq
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "rhino"))
import princess_butterfly_rhino as K
B, E = K.BF, K.EGG
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
T, S = B['T'], B['SPLIT']


def wire(segs, wp):
    w = wp.moveTo(*segs[0][1])
    for s in segs:
        w = w.lineTo(*s[2]) if s[0] == 'L' else w.threePointArc(s[2], s[3])
    return w


def slab(segs, z0, z1):
    return wire(segs, cq.Workplane("XY", origin=(0, 0, z0))).close().extrude(z1 - z0)


def footprint(side, z0, z1):
    pts = B['WING_PTS'] if side > 0 else K.mirror_pts(B['WING_PTS'])
    (cR, r), (cL, _) = K.hubs()
    c = cR if side > 0 else cL
    o = cq.Workplane("XY", origin=(0, 0, z0)).spline(pts, periodic=True).close().extrude(z1 - z0)
    d = cq.Workplane("XY", origin=(0, 0, z0)).center(*c).circle(r).extrude(z1 - z0)
    f = o.union(d)
    return f   # (Rhino applies the 2D root fillet; OCC merges these faces so it is skipped here)


def sweep_circle(pts, r, z, closed):
    path = cq.Workplane("XY", origin=(0, 0, z)).spline(pts, periodic=closed)
    if closed:
        path = path.close()
    p0 = pts[0]
    # tangent at start for the profile plane
    if closed:
        t = (pts[1][0] - pts[-1][0], pts[1][1] - pts[-1][1])
    else:
        t = (pts[1][0] - p0[0], pts[1][1] - p0[1])
    pl = cq.Plane(origin=(p0[0], p0[1], z), xDir=(0, 0, 1), normal=(t[0], t[1], 0))
    s = cq.Workplane(pl).circle(r).sweep(path)
    if not closed:
        for q in (pts[0], pts[-1]):
            s = s.union(cq.Workplane().add(cq.Solid.makeSphere(r, cq.Vector(q[0], q[1], z))))
    return s


def decor(side):
    m = (lambda p: p) if side > 0 else K.mirror_pts
    out = [sweep_circle(m(p), B['FRAME_R'], T, True) for p in (B['FRAME_UP'], B['FRAME_LO'])]
    out += [sweep_circle(m(p), B['VEIN_R'], T, False) for p in B['VEINS']]
    out += [cq.Workplane().add(cq.Solid.makeSphere(B['PEARL_R'], cq.Vector(x, y, T + B['PEARL_Z'])))
            for (x, y) in m(B['PEARLS'])]
    return out


def revolve_at(segs, x, y, z):
    return wire(segs, cq.Workplane("XZ")).close().revolve(360, (0, 0, 0), (0, 1, 0)).translate((x, y, z))


def wing(side, fit=B['LIP_FIT'], with_decor=True):
    w = footprint(side, 0, T)
    if side > 0:
        w = w.cut(footprint(-1, S, T + 1)).union(slab(K.lip_band(+1), S - 0.1, T))
        w = w.cut(slab(K.lip_band(-1, fit), -1, T + 1))
    else:
        w = w.cut(footprint(+1, -1, S)).union(slab(K.lip_band(-1), 0, S + 0.1))
        w = w.cut(slab(K.lip_band(+1, fit), -1, T + 1))
    if with_decor:
        for d in decor(side):
            w = w.union(d)
    bh = B['BOSS_H'] + 0.2
    rt = B['BOSS_D'] / 2
    rb = rt - bh * math.tan(math.radians(B['BOSS_DRAFT']))
    for (x, y) in B['BOSS_POS']:
        x *= side
        w = w.union(revolve_at(K.pin_profile(rb, rt, bh), x, y, -B['BOSS_H']))
        w = w.cut(revolve_at(K.hole_profile(B['CLIP_HOLE_D'] / 2, B['CLIP_HOLE_DEPTH']), x, y, -B['BOSS_H']))
    return w


def clip():
    c = wire(K.clip_outline(), cq.Workplane("YZ")).close().extrude(B['CLIP_W'])
    for y in B['CLIP_PIN_Y']:
        c = c.union(revolve_at(K.pin_profile(B['CLIP_PIN_D'] / 2, B['CLIP_PIN_D'] / 2, B['CLIP_PIN_H'] + 0.1, 0.35),
                               B['CLIP_W'] / 2, y, -0.1))
    return c


def clip_on_wing(c, side):
    x, y = B['BOSS_POS'][0]
    p = c.translate((x - B['CLIP_W'] / 2, y - B['CLIP_PIN_Y'][0], -B['BOSS_H']))
    return p.mirror("YZ") if side < 0 else p


vol = lambda s: sum(v.Volume() for v in s.solids().vals()) if s.solids().size() else 0.0

if __name__ == "__main__":
    R, L, C = wing(+1), wing(-1), clip()
    for n, p in (("P1_wing_R", R), ("P2_wing_L", L), ("P3_clip", C)):
        v = p.val(); bb = v.BoundingBox()
        print("%-10s valid=%s solids=%d vol=%.0f mm3 (ABS %.2f g) bbox %.1f x %.1f x %.1f" %
              (n, v.isValid(), p.solids().size(), v.Volume(), v.Volume() * 1.05e-3, bb.xlen, bb.ylen, bb.zlen))
        cq.exporters.export(p, os.path.join(OUT, n + ".step"))
        cq.exporters.export(p, os.path.join(OUT, n + ".stl"), tolerance=0.02, angularTolerance=0.1)

    # --- interlock checks (no decor / no fit, pure geometry)
    R0, L0 = wing(+1, 0.0, False), wing(-1, 0.0, False)
    print("assembled overlap, nominal (should be 0): %.4f mm3" % vol(R0.intersect(L0)))
    print("assembled overlap, press-fit LIP_FIT=%.2f: %.3f mm3" % (B['LIP_FIT'], vol(R.intersect(L))))
    for d, lab in (((-0.5, 0, 0), "pull apart along span (-X) 0.5"), ((0, 0.5, 0), "slide along Y 0.5"),
                   ((0, 0, 0.5), "lift L straight up 0.5 (assembly direction)")):
        print("  %-45s -> clash %.2f mm3 %s" % (lab, vol(R0.intersect(L0.translate(d))),
                                              "(locked)" if vol(R0.intersect(L0.translate(d))) > 0.5 else "(free)"))
    # relief stays on the wing's own top face (not in the overlap) and inside the outline
    for side, w in ((+1, R), (-1, L)):
        dec = decor(side)
        out_of_outline = sum(vol(d.cut(footprint(side, -1, 5))) for d in dec)
        in_overlap = sum(vol(d.intersect(footprint(-side, -1, 5))) for d in dec)
        print("decor side %+d: outside outline %.4f, inside overlap %.4f" % (side, out_of_outline, in_overlap))
    asm = {"wing_R": R, "wing_L": L, "clip_R": clip_on_wing(C, +1), "clip_L": clip_on_wing(C, -1)}
    print("clip/wing overlaps (pin press fit only):", ["%.2f" % vol(asm[a].intersect(asm[b]))
                                                        for a, b in (("wing_R", "clip_R"), ("wing_L", "clip_L"))])
    a = cq.Assembly()
    for n, p in asm.items():
        a.add(p, name=n, color=cq.Color(0.96, 0.6, 0.8) if "wing" in n else cq.Color(1, 1, 1))
        cq.exporters.export(p, os.path.join(OUT, "asm_" + n + ".stl"), tolerance=0.02, angularTolerance=0.1)
    a.save(os.path.join(OUT, "princess_butterfly_assembly.step"))
    bb = R.union(L).val().BoundingBox()
    print("assembled butterfly: %.1f x %.1f x %.1f mm (wings only)" % (bb.xlen, bb.ylen, bb.zlen))

    # --- packing in the real capsule (closed shell from the same script)
    def rev(segs):
        return wire(segs, cq.Workplane("XZ")).close().revolve(360, (0, 0, 0), (0, 1, 0))
    base = rev(K.egg_base_outer()).cut(rev(K.egg_base_inner()))
    cap = rev(K.egg_cap_outer()).cut(rev(K.egg_cap_inner()))
    shell = base.union(cap)
    env = rev(K.egg_base_outer()).union(rev(K.egg_cap_outer()))

    def centred(s, rz=False):
        s = s.rotate((0, 0, 0), (1, 0, 0), 90)
        if rz:
            s = s.rotate((0, 0, 0), (0, 0, 1), 180)
        b = s.val().BoundingBox()
        return s.translate((-(b.xmin + b.xmax) / 2, -(b.ymin + b.ymax) / 2, -(b.zmin + b.zmax) / 2)), b.ylen
    g, zc = 0.3, E['L_TOTAL'] / 2
    wr, tr = centred(R); wl, tl = centred(L); c1, tc = centred(C); c2, _ = centred(C, True)
    packed = {"wing_R": wr.translate((0, -(tr / 2 + g / 2), zc)), "wing_L": wl.translate((0, tl / 2 + g / 2, zc)),
              "clip_1": c1.translate((0, tl + g + tc / 2 + g, zc)),
              "clip_2": c2.translate((0, -(tr + g + tc / 2 + g), zc))}
    ok = True
    for n, s in packed.items():
        hit = vol(s.intersect(shell)); inside = vol(s.intersect(env)) / s.val().Volume()
        d = s.val().distance(shell.val())
        print("packed %-7s shell overlap=%.4f inside=%.4f clearance=%.2f" % (n, hit, inside, d))
        ok &= hit < 1e-6 and inside > 0.9999
        cq.exporters.export(s, os.path.join(OUT, "packed_" + n + ".stl"), tolerance=0.03)
    ks = list(packed)
    for i in range(4):
        for j in range(i + 1, 4):
            ok &= vol(packed[ks[i]].intersect(packed[ks[j]])) < 1e-6
    print("PACKED IN CAPSULE:", "OK" if ok else "FAIL")
    for n, s in (("base", base), ("cap", cap)):
        cq.exporters.export(s, os.path.join(OUT, "egg_%s.stl" % n), tolerance=0.03)
