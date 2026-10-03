"""Packing check: all 4 parts inside the Kinder capsule (inner space, conservative).
Capsule axis = Z. Inner space model (from the drawing, with ~0.3 mm safety):
  radius 15.3 (lower half inner R ~15.9), length 42.4 (outer 45.32 - 2x0.68 wall),
  end corner fillet R10.5 (drawing R11.18 outer), flat ends (dome ignored -> conservative)."""
import math, os
import numpy as np
import cadquery as cq
import build as B

R_IN, L_IN, R_C = 15.3, 42.4, 10.5
OUT = B.OUT


def capsule_inner():
    prof = (cq.Workplane("XZ").moveTo(0, -L_IN / 2).lineTo(R_IN, -L_IN / 2)
            .lineTo(R_IN, L_IN / 2).lineTo(0, L_IN / 2).close())
    s = prof.revolve(360, (0, 0, 0), (0, 1, 0))
    return s.edges().fillet(R_C) if False else s


def inside(p):
    r = math.hypot(p[0], p[1]); z = abs(p[2])
    if r > R_IN + 1e-6 or z > L_IN / 2 + 1e-6:
        return False
    if r > R_IN - R_C and z > L_IN / 2 - R_C:
        return math.hypot(r - (R_IN - R_C), z - (L_IN / 2 - R_C)) <= R_C + 1e-6
    return True


def place(shape, rot_seq, t):
    s = shape
    for axis, ang in rot_seq:
        ax = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[axis]
        s = s.rotate((0, 0, 0), ax, ang)
    return s.translate(t)


def centre_xy_z(s):
    bb = s.val().BoundingBox()
    return s.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -(bb.zmin + bb.zmax) / 2))


if __name__ == "__main__":
    wr, wl, cl = B.wing_R(), B.wing_L(), B.clip()
    # wing: y(body axis) -> Z, z(thickness) -> Y   == rotate +90 about X
    W = lambda s: centre_xy_z(s.rotate((0, 0, 0), (1, 0, 0), 90))
    C = lambda s: centre_xy_z(s.rotate((0, 0, 0), (1, 0, 0), 90))
    wrp = W(wr); wlp = W(wl); cp = C(cl)
    def thick(s): bb = s.val().BoundingBox(); return bb.ylen
    gap = 0.3
    ty_r, ty_l = thick(wrp), thick(wlp)
    packed = {
        "wing_R": wrp.translate((0, -(ty_r / 2 + gap / 2), 0)),
        "wing_L": wlp.translate((0, ty_l / 2 + gap / 2, 0)),
    }
    yc = ty_l + gap + thick(cp) / 2 + gap
    packed["clip_1"] = cp.translate((0, yc, 0))
    packed["clip_2"] = cp.rotate((0, 0, 0), (0, 0, 1), 180).translate((0, -(ty_r + gap + thick(cp) / 2 + gap), 0))

    ok = True
    for n, s in packed.items():
        verts = [v.toTuple() for v in s.val().Vertices()]
        # densify: tessellate for curved faces
        vs, _ = s.val().tessellate(0.05)
        pts = [v.toTuple() for v in vs]
        bad = [p for p in pts if not inside(p)]
        bb = s.val().BoundingBox()
        print(f"{n:7s} inside={not bad}  outside_pts={len(bad)}  X[{bb.xmin:.1f},{bb.xmax:.1f}] "
              f"Y[{bb.ymin:.1f},{bb.ymax:.1f}] Z[{bb.zmin:.1f},{bb.zmax:.1f}]")
        if bad:
            ok = False
            far = max(bad, key=lambda p: math.hypot(p[0], p[1]))
            print("   worst", [round(c, 2) for c in far])
    names = list(packed)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            v = packed[names[i]].intersect(packed[names[j]]).val().Volume()
            if v > 1e-6:
                ok = False
                print("  OVERLAP", names[i], names[j], v)
    print("PACKING OK" if ok else "PACKING FAIL")
    for n, s in packed.items():
        cq.exporters.export(s, os.path.join(OUT, "pack_" + n + ".stl"), tolerance=0.02, angularTolerance=0.1)
    # capsule inner volume (for visualisation)
    pts = [(0, -L_IN / 2)]
    for k in range(0, 31):
        a = math.pi / 2 * k / 30
        pts.append(((R_IN - R_C) + R_C * math.sin(a), -(L_IN / 2 - R_C) - R_C * math.cos(a)))
    for k in range(0, 31):
        a = math.pi / 2 * k / 30
        pts.append(((R_IN - R_C) + R_C * math.cos(a), (L_IN / 2 - R_C) + R_C * math.sin(a)))
    pts.append((0, L_IN / 2))
    cap = cq.Workplane("XZ").polyline(pts).close().revolve(360, (0, 0, 0), (0, 1, 0))
    cq.exporters.export(cap, os.path.join(OUT, "capsule_inner_space.stl"), tolerance=0.05)
    cq.exporters.export(cap, os.path.join(OUT, "capsule_inner_space.step"))
