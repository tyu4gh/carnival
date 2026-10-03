"""
Kinder Surprise butterfly hair-clip toy  (4 parts, ABS, no metal)
Generates STEP/STL/3DM for Rhino + packing check inside the capsule.

Coordinate system of the assembled butterfly (mm):
  X = wing span (right wing +X), Y = body axis (head +Y), Z = up (top face of wings +Z)
Parts:
  P1  Wing R (right wing, has lap tab + 2 joining pins)
  P2  Wing L (left wing, has 2 joining holes)
  P3  Clip (x2, identical part, one mold cavity used twice)
"""
import math, os, sys
import cadquery as cq

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- parameters
BODY_W, BODY_Y0, BODY_Y1, BODY_H = 8.0, -13.0, 14.0, 5.0
LAP_Z = 2.2                 # split height of the lap joint
PLATE_Z0, PLATE_T = 2.2, 1.8  # wing plate z 2.2 .. 4.0
JOIN_PIN_D, JOIN_HOLE_D, JOIN_PIN_H, JOIN_HOLE_DEPTH = 2.05, 2.00, 1.8, 2.0
JOIN_PIN_POS = [(-2.0, -6.0), (-2.0, 6.0)]

BOSS_D, BOSS_Z0 = 5.0, 0.7          # clip boss under the wing (z 0.7 .. 2.2)
CLIP_PIN_D, CLIP_HOLE_D = 2.25, 2.20
CLIP_PIN_H, CLIP_HOLE_DEPTH = 2.1, 2.3
BOSS_POS = [(10.5, -6.0), (10.5, 10.0)]   # right wing (mirror for left)

CLIP_W, CLIP_L, CLIP_T = 7.0, 24.0, 1.4

# right-wing outline (one closed spline: fore-wing + hind-wing)
WING_PTS = [(2.5, 4), (5, 12), (10, 16.5), (16, 17.5), (21, 15), (22.5, 10),
            (19, 4.5), (14, 1.0), (16.5, -3), (18, -9), (15.5, -14), (9, -14.5),
            (4.5, -10), (2.5, -4)]
SPOTS = [((15.5, 11.0), 3.2), ((12.5, -8.5), 2.4), ((7.5, 7.0), 1.6)]  # raised 0.4 decor


def mirror_x(shape):
    return shape.mirror("YZ")


# ---------------------------------------------------------------- wings
def full_body():
    b = (cq.Workplane("XY").center(0, (BODY_Y0 + BODY_Y1) / 2)
         .slot2D(BODY_Y1 - BODY_Y0, BODY_W, angle=90).extrude(BODY_H))
    b = b.edges(">Z").fillet(2.0).edges("<Z").fillet(0.6)
    # segment grooves on the abdomen (decor, straight pull)
    for y in (-9.0, -6.0, -3.0):
        g = cq.Workplane("XY").box(BODY_W + 2, 0.6, 0.5).translate((0, y, BODY_H - 0.25))
        b = b.cut(g)
    # eyes
    for x in (-2.0, 2.0):
        b = b.cut(cq.Workplane("XY").circle(0.8).extrude(0.4).translate((x, 11.0, BODY_H - 0.6)))
    return b


def wing_half(side):
    """plate + spots + antenna + clip bosses for side +1 (right)."""
    plate = (cq.Workplane("XY").workplane(offset=PLATE_Z0)
             .spline(WING_PTS, periodic=True).close().extrude(PLATE_T))
    try:
        plate = plate.faces(">Z").edges().fillet(0.5)
    except Exception:
        pass
    for (c, r) in SPOTS:
        plate = plate.union(cq.Workplane("XY").workplane(offset=PLATE_Z0 + PLATE_T)
                            .center(*c).circle(r).extrude(0.4))
        plate = plate.cut(cq.Workplane("XY").workplane(offset=PLATE_Z0 + PLATE_T + 0.2)
                          .center(*c).circle(r * 0.45).extrude(0.4))
    # antenna (rounded, thick, no sharp tip)
    path = cq.Workplane("XY").spline([(1.6, 12.0), (3.0, 16.5), (5.8, 19.2)])
    ant = (cq.Workplane("XZ", origin=(1.6, 12.0, 3.7)).circle(0.9)
           .sweep(cq.Workplane("XY", origin=(0, 0, 3.7))
                  .spline([(1.6, 12.0), (3.0, 16.5), (5.8, 19.2)])))
    ant = ant.union(cq.Workplane("XY").sphere(1.5).translate((5.8, 19.2, 3.7)))
    plate = plate.union(ant)
    # clip bosses with pin holes
    for (x, y) in BOSS_POS:
        boss = (cq.Workplane("XY").workplane(offset=BOSS_Z0).center(x, y)
                .circle(BOSS_D / 2).extrude(PLATE_Z0 - BOSS_Z0 + 0.2, taper=1))
        plate = plate.union(boss)
        hole = (cq.Workplane("XY").workplane(offset=BOSS_Z0).center(x, y)
                .circle(CLIP_HOLE_D / 2).extrude(CLIP_HOLE_DEPTH))
        plate = plate.cut(hole)
        # lead-in chamfer on hole
        plate = plate.cut(cq.Workplane("XY").workplane(offset=BOSS_Z0).center(x, y)
                          .circle(CLIP_HOLE_D / 2 + 0.3).workplane(offset=0.3)
                          .circle(CLIP_HOLE_D / 2).loft())
    if side < 0:
        plate = mirror_x(plate)
    return plate


def big_box(x0, x1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, 60, z1 - z0).translate(((x0 + x1) / 2, 0, (z0 + z1) / 2))


def wing_R():
    body = full_body()
    upper_r = body.intersect(big_box(0, 10, LAP_Z, 10))
    lower = body.intersect(big_box(-10, 10, -1, LAP_Z))
    part = upper_r.union(lower).union(wing_half(+1))
    # trim anything of the plate that crossed into x<0 above the lap (keeps split face clean)
    part = part.cut(big_box(-10, 0, LAP_Z, 10))
    # joining pins (on top of the lap tab)
    for (x, y) in JOIN_PIN_POS:
        pin = (cq.Workplane("XY").workplane(offset=LAP_Z).center(x, y)
               .circle(JOIN_PIN_D / 2).extrude(JOIN_PIN_H - 0.3, taper=0.5)
               .faces(">Z").workplane().circle(JOIN_PIN_D / 2 - 0.02)
               .workplane(offset=0.3).circle(JOIN_PIN_D / 2 - 0.3).loft())
        part = part.union(pin)
    # core-out the thick upper body from below (uniform wall, no sink marks)
    part = part.cut(cq.Workplane("XY").center(1.7, -1.0).rect(1.8, 17).extrude(3.4))
    return part


def wing_L():
    body = full_body()
    upper_l = body.intersect(big_box(-10, 0, LAP_Z, 10))
    part = upper_l.union(wing_half(-1))
    part = part.cut(big_box(-0.0, 10, -1, 10))      # nothing past split face
    part = part.cut(big_box(-10, 10, -1, LAP_Z).intersect(
        cq.Workplane("XY").box(BODY_W, BODY_Y1 - BODY_Y0 + 2, 10)))  # clear lap zone
    for (x, y) in JOIN_PIN_POS:
        part = part.cut(cq.Workplane("XY").workplane(offset=LAP_Z).center(x, y)
                        .circle(JOIN_HOLE_D / 2).extrude(JOIN_HOLE_DEPTH))
        part = part.cut(cq.Workplane("XY").workplane(offset=LAP_Z).center(x, y)
                        .circle(JOIN_HOLE_D / 2 + 0.3).workplane(offset=0.3)
                        .circle(JOIN_HOLE_D / 2).loft())
    return part


# ---------------------------------------------------------------- clip
def clip():
    """One-piece ABS spring clip. Profile drawn in YZ, extruded along X.
    Mold: straight pull along X, parting plane at x = CLIP_W/2 (through pin axes)."""
    t, L = CLIP_T, CLIP_L
    cz = -t - 1.3                 # bend centre (gap at bend 2.6)
    ri, ro = 1.3, 1.3 + t
    tip_y, tab_y = 3.0, -3.0
    gap_tip = 1.2
    top_tongue_tip = -t - gap_tip
    s = cq.Workplane("YZ")
    # top arm
    prof = s.polyline([(0, 0), (L, 0), (L, -t), (0, -t)]).close().extrude(CLIP_W)
    # bend (half annulus, +Y side)
    ring = (cq.Workplane("YZ").center(L, cz).circle(ro).circle(ri).extrude(CLIP_W)
            .cut(cq.Workplane("YZ").center(L - ro, cz).rect(2 * ro, 2 * ro + 1).extrude(CLIP_W)))
    prof = prof.union(ring)
    # tongue: from bend bottom (L, cz-ri .. cz-ro) to tip, rising
    z_root_top = cz - ri
    tongue = (cq.Workplane("YZ").polyline([
        (L + 0.01, z_root_top), (tip_y, top_tongue_tip),
        (0.5, top_tongue_tip - 0.6), (tab_y, top_tongue_tip - 2.0),          # flared lead-in / thumb tab
        (tab_y, top_tongue_tip - 2.0 - t), (0.5, top_tongue_tip - 0.6 - t),
        (tip_y, top_tongue_tip - t), (L + 0.01, z_root_top - t)]).close().extrude(CLIP_W))
    prof = prof.union(tongue)
    # grip teeth on tongue (triangular ridges, extruded along X -> straight pull)
    for i in range(7):
        y = 6.0 + i * 2.2
        ztop = z_root_top + (top_tongue_tip - z_root_top) * (L - y) / (L - tip_y)
        tooth = (cq.Workplane("YZ").polyline([(y - 0.7, ztop - 0.05), (y + 0.7, ztop - 0.05),
                                             (y, ztop + 0.6)]).close().extrude(CLIP_W))
        prof = prof.union(tooth)
    # round the thumb tab corners in plan
    try:
        prof = prof.edges("|Z").edges("<Y").fillet(1.5)
    except Exception:
        pass
    # mounting pins (axis Z, centred on parting plane x = W/2)
    for y in (4.0, 20.0):
        pin = (cq.Workplane("XY").center(CLIP_W / 2, y).circle(CLIP_PIN_D / 2).extrude(CLIP_PIN_H - 0.35)
               .faces(">Z").workplane().circle(CLIP_PIN_D / 2)
               .workplane(offset=0.35).circle(CLIP_PIN_D / 2 - 0.35).loft())
        prof = prof.union(pin)
    return prof


def clip_on_wing(c, side):
    """place clip under a wing: clip pin (y=4) -> boss (10.5,-6)."""
    x, y = BOSS_POS[0]
    placed = c.translate((x - CLIP_W / 2, y - 4.0, BOSS_Z0))
    return placed if side > 0 else mirror_x(placed)


# ---------------------------------------------------------------- build
if __name__ == "__main__":
    wr, wl, cl = wing_R(), wing_L(), clip()
    parts = {"P1_wing_R": wr, "P2_wing_L": wl, "P3_clip": cl}
    for n, p in parts.items():
        s = p.val()
        print(n, "valid", s.isValid(), "solids", len(p.solids().vals()),
              "vol %.1f mm3" % s.Volume(), "mass ABS %.2f g" % (s.Volume() * 1.05e-3),
              "bbox", [round(v, 2) for v in (s.BoundingBox().xlen, s.BoundingBox().ylen, s.BoundingBox().zlen)])
        cq.exporters.export(p, os.path.join(OUT, n + ".step"))
        cq.exporters.export(p, os.path.join(OUT, n + ".stl"), tolerance=0.02, angularTolerance=0.1)
    asm = {"wing_R": wr, "wing_L": wl,
           "clip_R": clip_on_wing(cl, +1), "clip_L": clip_on_wing(cl, -1)}
    import pickle
    for n, p in asm.items():
        cq.exporters.export(p, os.path.join(OUT, "asm_" + n + ".stl"), tolerance=0.02, angularTolerance=0.1)
    # interference check in assembly
    names = list(asm)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            v = asm[names[i]].intersect(asm[names[j]]).val().Volume() if True else 0
            print("overlap", names[i], names[j], "%.3f" % v)
    a = cq.Assembly()
    cols = {"wing_R": (0.95, 0.45, 0.7), "wing_L": (0.95, 0.45, 0.7), "clip_R": (1, 1, 1), "clip_L": (1, 1, 1)}
    for n, p in asm.items():
        a.add(p, name=n, color=cq.Color(*cols[n]))
    a.save(os.path.join(OUT, "butterfly_assembly.step"))
