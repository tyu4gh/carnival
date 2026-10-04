# -*- coding: utf-8 -*-
"""
Kinder Surprise capsule + "Fairytale Princess" butterfly hair clip, built from scratch with RhinoCommon.

How to run (Rhino 7 / 8 / 9 WIP, Windows or Mac):
    Rhino command line  ->  RunPythonScript  ->  pick this file
    or ScriptEditor -> open this file -> Run (IronPython 2 or CPython 3 both work)

Everything is parametric: edit EGG / BF below and run again.
Objects created by a previous run (layer tree "KinderToy") are deleted first.

Toy v3 (4 parts, injection moulded ABS, no metal, all straight-pull tools). Wing shape from the
user's model buttclip_Ver.1.1.3dm; the two wing roots overlap in a lens-shaped zone:
    P1 right wing  - MALE: root edge is a thin smooth tongue that slides in from the right UNDER
                     the left wing; a small jewel on the tongue clicks into the middle heart window
    P2 left wing   - FEMALE: thicker root band with a side slot under its upper lip; 3 heart
                     windows in the lip (2 with support tabs below = straight-pull shut-offs)
    P3 clip x2     - identical one-piece ABS spring clip, press-fits under either wing

Output layers (parent "KinderToy"):
    Egg_Closed / Egg_HalfOpen / Egg_Open      capsule with wall thickness, 3 hinge states
    Egg_Closed_Section                        closed capsule cut in half + packed toy inside
    Butterfly_Assembly                        4 parts assembled
    Butterfly_Parts                           P1, P2, P3 laid out
    Packed_In_Egg                             4 parts in their packing position (inside Egg_Closed)
    _Debug                                    only filled if a boolean failed (see command line)

Units: all parameters are millimetres. If the document is in another unit the result is scaled.
The geometry maths (profiles, outlines, joint, packing) is plain Python and is cross-checked
outside Rhino by ../verify_rhino_math.py and ../verify_princess.py (CadQuery / OpenCascade).
"""
from __future__ import division, print_function
import math

try:
    import Rhino
    import Rhino.Geometry as rg
    import scriptcontext as sc
    import System
    from System.Collections.Generic import List
    RHINO = True
except ImportError:          # imported by the CPython verifier outside Rhino
    RHINO = False

# =====================================================================================
# PARAMETERS - EGG CAPSULE  (dimensions read from the Kinder drawing, mm)
# closed state frame: capsule axis = world Z, base bottom apex at z = 0, cap top at z = L_TOTAL
# =====================================================================================
EGG = dict(
    L_TOTAL=45.32,        # closed overall length
    T=0.68,               # wall thickness
    R_DOME=35.31,         # end dome radius (both ends)
    # base (lower half)
    B_R=17.03,            # body outer radius
    B_CORNER=11.51,       # corner radius between end dome and side wall (outer)
    Z_SEAM=27.9,          # seam: base shoulder / cap rim (base depth to shoulder)
    LIP_R=17.44,          # outer radius of base lip under the seam
    LIP_H=1.2,            # lip height
    NECK_R=16.02,         # neck outer radius (goes inside the cap)
    NECK_H=8.0,           # neck height above the seam
    NECK_CH=0.3,          # lead-in chamfer at neck top
    # cap (upper half)
    C_R=17.32,            # cap outer radius
    C_CORNER=11.18,       # corner radius (outer)
    RIM_CH=0.66,          # rim inner chamfer length (axial)
    RIM_CH_ANG=30.0,      # rim inner chamfer angle to axis (deg)
    # snap: rib inside the cap engages a groove on the base neck
    SNAP_DZ=4.3,          # rib / groove height above the seam
    RIB_R=15.90,          # rib inner radius (0.12 interference over the neck)
    GROOVE_R=0.4,         # groove tool (torus minor) radius
    GROOVE_DEPTH=0.15,    # groove depth into the neck
    # living hinge (on -X side of the capsule)
    H_E=0.9,              # hinge pivot distance outside the lip
    H_RHO=2.2,            # hinge strap bend radius (strap centre line)
    H_ATT=60.0,           # attach angle of strap ends (deg from +X, closed state)
    H_T=0.5,              # strap thickness
    H_W=6.0,              # strap width (along Y)
    H_PAD=1.0,            # attach pad height
    # states: opening angle of the cap around the hinge (0 = closed, 180 = as moulded)
    STATES=[("Egg_Closed", 0.0), ("Egg_HalfOpen", 90.0), ("Egg_Open", 180.0)],
    STATE_DY=75.0,        # spacing of the 3 states along Y
)

# =====================================================================================
# PARAMETERS - "FAIRYTALE PRINCESS" BUTTERFLY HAIR CLIP v3  (4 parts, ABS, no metal)
# assembled frame: X = span (right wing +X), Y = up the head, Z = up. Both wings: plate z 0..T.
# Wing shape = the user's model buttclip_Ver.1.1.3dm (layer "wing right", mirrored for the left),
# slid together by OVERLAP so the two root edges overlap in a lens-shaped zone:
#   left wing  (P2, FEMALE): thicker root band + side slot open towards +X, upper lip on top,
#                            3 heart windows in the lip (2 with support tabs below, 1 snap window)
#   right wing (P1, MALE)  : thin smooth tongue (TONGUE_T) slides in from the right UNDER the
#                            left wing's lip; a small jewel on the tongue clicks into the heart.
# =====================================================================================
BF = dict(
    # right-wing outline, through-points (user model, root edge at x = 0.25, centre gap 0.5 mm)
    WING_PTS=[(0.25, -0.74), (0.84, -4.09), (2.45, -7.1), (4.67, -9.71), (7.35, -11.83),
              (10.31, -13.56), (13.45, -14.91), (16.81, -15.4), (19.38, -13.39), (19.56, -10.0),
              (18.57, -6.73), (18.22, -3.51), (20.58, -1.04), (22.46, 1.82), (23.83, 4.96),
              (24.83, 8.23), (25.15, 11.63), (23.85, 14.73), (20.6, 15.42), (17.27, 14.65),
              (14.06, 13.45), (11.02, 11.87), (8.21, 9.91), (5.62, 7.68), (3.21, 5.23), (1.13, 2.52)],
    SAMPLES=6,                   # Catmull-Rom samples per span (dense outline used everywhere)
    OVERLAP=7.5,                 # each wing slides OVERLAP/2 towards the centre
    T=2.0,                       # wing plate thickness (as the user's model)
    FILLET_TOP=0.8, FILLET_BOT=0.8,   # rounded rim like the user's model
    # ---- joint (all z in the wing frame, plate z 0..T)
    CLR=0.15,                    # clearance tongue <-> slot / step
    TONGUE_T=0.95,               # male tongue thickness (z 0..TONGUE_T)
    LIP_Z0=1.0,                  # female: slot ceiling = underside of the upper lip (lip z LIP_Z0..T)
    FLOOR_Z=-0.1,                # female: top of the support tabs (slot floor)
    THICK_Z0=-1.2,               # female: bottom of the thicker root band
    THICK_BAND=1.8,              # female: band width around the slot (behind the tongue tip)
    THICK_INSET=1.0,             # band stays this far inside the left outline (clear of the rim fillet)
    TAB_INSET=0.12,              # tab = disc on the heart's inscribed circle, this much smaller
    TAB_Z0=-1.05,                # tab bottom (just above THICK_Z0: no coplanar faces)
    HEART_W=2.8,                 # tab-window hearts (width)
    HEART_TABS=[-4.6, 3.0],      # y of the 2 support-tab hearts; they straddle the slot back wall
    HEART_TAB_IN=0.2,            # tab-heart centre this far inside the slot from the back wall
    GEM_HEART_W=3.8, GEM_Y=-0.9,  # snap window heart (in the middle of the lens)
    GEM_H=0.35, GEM_CLR=0.1,     # jewel on the tongue: 45 deg frustum, sized to the heart's
                                 # largest inscribed circle minus GEM_CLR at the lip underside
    EDGE_SOFT=0.25,              # fillet of window / step top edges
    # ---- raised decoration for the UV colour-change coating (half-round beads, ~0.3 high)
    DECO_R=0.30,                 # bead radius (pipe centre on the top face -> 0.30 high)
    BORDER_OFF=1.7,              # inner border bead offset from the outline
    TRIM=1.0,                    # decoration stops this far from the other wing's footprint
    VEINS=[[(9.0, 3.6), (12.4, 6.6), (16.0, 9.2), (19.4, 11.0), (21.6, 10.6), (21.9, 8.6),
            (20.4, 7.9), (19.5, 9.0)],                                      # fore-wing scroll
           [(10.4, 1.6), (13.8, 2.9), (17.0, 4.3), (19.6, 5.7)],            # fore-wing vein
           [(8.6, -3.4), (11.2, -6.4), (13.8, -9.4), (16.0, -11.2), (17.2, -9.9), (16.2, -8.7),
            (15.1, -9.4)],                                                  # hind-wing scroll
           [(10.8, -2.4), (13.4, -3.9), (15.6, -5.8)]],                     # hind-wing vein
    PEARLS=[(19.5, 9.0, 0.55), (15.1, -9.4, 0.5)],     # pearls at the scroll ends
    BORDER_PEARL_R=0.45, BORDER_PEARL_PITCH=5.0,       # pearls strung on the border bead
    # ---- clip interface (same one-piece ABS clip, shorter for this wing)
    BOSS_D=5.0, BOSS_H=1.5, BOSS_DRAFT=1.0,
    CLIP_PIN_D=2.25, CLIP_HOLE_D=2.20, CLIP_PIN_H=2.1, CLIP_HOLE_DEPTH=2.3,
    BOSS_POS=[(10.5, -9.0), (10.5, 5.0)],      # right wing, assembled frame; mirrored for the left
    CLIP_W=7.0, CLIP_L=22.0, CLIP_T=1.4, CLIP_PIN_Y=[4.0, 18.0],
    ASM_OFFSET=(110.0, 0.0, 0.0),
    PARTS_OFFSET=(170.0, 0.0, 0.0),
)

# packing in the closed capsule: part, (rot about X deg, rot about Z deg, dx, dy, dz) applied to
# the part's assembled-frame geometry; found and verified (no clash with the real shell) by
# ../verify_princess.py
PACK = [("R", (-90, 0, -8.973, -2.650, 22.631)),
        ("L", (90, 0, 8.973, 2.650, 22.689)),
        ("C", (90, 0, -3.500, 6.650, 11.810)),
        ("C", (90, 180, 3.500, -6.650, 11.810))]

EPS = 0.05   # overlap used so that booleans never meet coplanar / tangent faces


# =====================================================================================
# PURE GEOMETRY MATHS (no Rhino) - profiles as segment lists
#   ('L', p0, p1)        line
#   ('A', p0, pm, p1)    arc through 3 points
# points are 2D tuples; for revolved parts (r, z), for the clip (y, z)
# =====================================================================================
def _unit(v):
    l = math.hypot(v[0], v[1])
    return (v[0] / l, v[1] / l)


def _add(p, v, s=1.0):
    return (p[0] + v[0] * s, p[1] + v[1] * s)


def end_cap(R_side, R_corner, R_dome, z_apex, sign, off):
    """Dome + corner arcs of a capsule end, offset inward by `off`.
    sign=+1: end at the bottom (dome centre above apex), -1: end at the top.
    Returns (segments from the apex to the start of the straight side, z of side start)."""
    zc_d = z_apex + sign * R_dome
    xc = R_side - R_corner
    dz = math.sqrt((R_dome - R_corner) ** 2 - xc ** 2)
    zc_c = zc_d - sign * dz
    u = _unit((xc, zc_c - zc_d))                    # dome centre -> corner centre
    rd, rc = R_dome - off, R_corner - off
    apex = (0.0, zc_d - sign * rd)
    t1 = _add((0.0, zc_d), u, rd)
    m1 = _add((0.0, zc_d), _unit(_add((0.0, -sign), u)), rd)
    t2 = (xc + rc, zc_c)
    m2 = _add((xc, zc_c), _unit(_add(u, (1.0, 0.0))), rc)
    return [('A', apex, m1, t1), ('A', t1, m2, t2)], zc_c


def chain(start_segs, pts):
    """append straight lines through pts to an existing segment list"""
    segs = list(start_segs)
    cur = segs[-1][-1]
    for p in pts:
        segs.append(('L', cur, p))
        cur = p
    return segs


def egg_base_outer(E=EGG):
    e, zs = end_cap(E['B_R'], E['B_CORNER'], E['R_DOME'], 0.0, +1, 0.0)
    top = E['Z_SEAM'] + E['NECK_H']
    lip0 = E['Z_SEAM'] - E['LIP_H']
    dr = E['LIP_R'] - E['B_R']
    return chain(e, [(E['B_R'], lip0), (E['LIP_R'], lip0 + dr), (E['LIP_R'], E['Z_SEAM']),
                     (E['NECK_R'], E['Z_SEAM']), (E['NECK_R'], top - E['NECK_CH']),
                     (E['NECK_R'] - E['NECK_CH'], top), (0.0, top)])


def egg_base_inner(E=EGG):
    t = E['T']
    e, zs = end_cap(E['B_R'], E['B_CORNER'], E['R_DOME'], 0.0, +1, t)
    top = E['Z_SEAM'] + E['NECK_H'] + 1.0
    # 45 deg inner step below the seam: shoulder wall stays >= T everywhere
    return chain(e, [(E['B_R'] - t, E['Z_SEAM'] - 1.0), (E['NECK_R'] - t, E['Z_SEAM']),
                     (E['NECK_R'] - t, top), (0.0, top)])


def egg_cap_outer(E=EGG):
    e, zs = end_cap(E['C_R'], E['C_CORNER'], E['R_DOME'], E['L_TOTAL'], -1, 0.0)
    return chain(e, [(E['C_R'], E['Z_SEAM']), (0.0, E['Z_SEAM'])])


def egg_cap_inner(E=EGG):
    t = E['T']
    e, zs = end_cap(E['C_R'], E['C_CORNER'], E['R_DOME'], E['L_TOTAL'], -1, t)
    ri = E['C_R'] - t
    ch_r = E['RIM_CH'] * math.tan(math.radians(E['RIM_CH_ANG']))
    zb = E['Z_SEAM'] - 1.0
    return chain(e, [(ri, E['Z_SEAM'] + E['RIM_CH']), (ri + ch_r, E['Z_SEAM']),
                     (ri + ch_r, zb), (0.0, zb)])


def egg_snap_rib(E=EGG):
    """closed (r, z) polygon of the rib inside the cap (lead-in on the rim side)"""
    ri = E['C_R'] - E['T'] + EPS
    zr = E['Z_SEAM'] + E['SNAP_DZ']
    pts = [(ri, zr - 1.0), (E['RIB_R'], zr - 0.2), (E['RIB_R'], zr + 0.2), (ri, zr + 0.6)]
    return [('L', pts[i], pts[(i + 1) % 4]) for i in range(4)]


def hinge_pivot(E=EGG):
    """(x, z) of the hinge axis (axis direction = Y)"""
    return (-(E['LIP_R'] + E['H_E']), E['Z_SEAM'])


def hinge_attach(E=EGG):
    """closed-state attach points of strap on base and on cap, and pad boxes (x0,x1,z0,z1)"""
    hx, hz = hinge_pivot(E)
    a = math.radians(E['H_ATT'])
    pb = (hx + E['H_RHO'] * math.cos(-a), hz + E['H_RHO'] * math.sin(-a))
    pc = (hx + E['H_RHO'] * math.cos(a), hz + E['H_RHO'] * math.sin(a))
    h = E['H_PAD'] / 2
    pad_b = (pb[0] - 0.3, -(E['B_R'] - E['T'] / 2), pb[1] - h, pb[1] + h)
    pad_c = (pc[0] - 0.3, -(E['C_R'] - E['T'] / 2), pc[1] - h, pc[1] + h)
    return pb, pc, pad_b, pad_c


def hinge_strap(theta_deg, E=EGG):
    """closed (x, z) outline of the bent strap for cap opening angle theta.
    The strap runs clockwise around the pivot from the base attach angle (-H_ATT)
    to the rotated cap attach angle (H_ATT + theta - 360)."""
    hx, hz = hinge_pivot(E)
    a0 = -E['H_ATT']
    a1 = E['H_ATT'] + theta_deg - 360.0
    am = (a0 + a1) / 2
    ro, ri = E['H_RHO'] + E['H_T'] / 2, E['H_RHO'] - E['H_T'] / 2

    def P(r, a):
        return (hx + r * math.cos(math.radians(a)), hz + r * math.sin(math.radians(a)))
    return [('A', P(ro, a0), P(ro, am), P(ro, a1)), ('L', P(ro, a1), P(ri, a1)),
            ('A', P(ri, a1), P(ri, am), P(ri, a0)), ('L', P(ri, a0), P(ro, a0))]


def clip_outline(B=BF):
    """closed (y, z) outline of the one-piece clip: top arm + U bend + toothed tongue + thumb tab.
    Extruded along X by CLIP_W. Mould: straight pull along X, parting plane at x = CLIP_W/2."""
    t, L = B['CLIP_T'], B['CLIP_L']
    cz = -t - 1.3
    ri, ro = 1.3, 1.3 + t
    tip_y, tab_y = 3.0, -3.0
    ttt = -t - 1.2                      # tongue top at tip (gap 1.2)
    zrt = cz - ri                       # tongue top at root
    segs = [('L', (0.0, 0.0), (L, 0.0)),
            ('A', (L, 0.0), (L + ro, cz), (L, cz - ro))]
    pts = [(tip_y, ttt - t), (0.5, ttt - 0.6 - t), (tab_y, ttt - 2.0 - t),
           (tab_y, ttt - 2.0), (0.5, ttt - 0.6), (tip_y, ttt)]

    def ztop(y):
        return zrt + (ttt - zrt) * (L - y) / (L - tip_y)
    for i in range(7):                  # 7 grip teeth, 0.6 high, pitch 2.2
        y = 6.0 + i * 2.2
        pts += [(y - 0.7, ztop(y - 0.7)), (y, ztop(y) + 0.6), (y + 0.7, ztop(y + 0.7))]
    pts.append((L, zrt))
    segs = chain(segs, pts)
    segs.append(('A', (L, zrt), (L + ri, cz), (L, cz + ri)))
    segs = chain(segs, [(0.0, -t), (0.0, 0.0)])
    return segs


def pin_profile(r_bot, r_top, h, chamfer=0.0, z0=0.0):
    """(r, z) open profile axis -> axis of a (tapered, top-chamfered) pin"""
    pts = [(0.0, z0), (r_bot, z0)]
    if chamfer > 0:
        pts += [(r_top, z0 + h - chamfer), (r_top - chamfer, z0 + h)]
    else:
        pts += [(r_top, z0 + h)]
    pts.append((0.0, z0 + h))
    return [('L', pts[i], pts[i + 1]) for i in range(len(pts) - 1)]


def hole_profile(r, depth, chamfer=0.3):
    """(r, z) cutter profile of a blind hole entering at z=0 going +z, chamfered entry"""
    pts = [(0.0, -0.2), (r + chamfer + 0.2, -0.2), (r, chamfer), (r, depth), (0.0, depth)]
    return [('L', pts[i], pts[i + 1]) for i in range(len(pts) - 1)]


def check_chain(segs, closed=False, tol=1e-6):
    """continuity check used by the verifier"""
    for a, b in zip(segs, segs[1:] + (segs[:1] if closed else [])):
        pa, pb = a[-1], b[1]
        if math.hypot(pa[0] - pb[0], pa[1] - pb[1]) > tol:
            return False
    return True


# ---------------- princess butterfly v3 maths (plain python, no numpy) ----------------
def cr_closed(pts, n):
    """closed centripetal Catmull-Rom through pts, n samples per span"""
    m = len(pts)
    out = []
    for i in range(m):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % m], pts[(i + 2) % m]

        def tj(ti, a, b):
            return ti + max(math.hypot(b[0] - a[0], b[1] - a[1]), 1e-9) ** 0.5
        t0 = 0.0
        t1 = tj(t0, p0, p1)
        t2 = tj(t1, p1, p2)
        t3 = tj(t2, p2, p3)
        for k in range(n):
            t = t1 + (t2 - t1) * k / n

            def lerp(a, b, ta, tb):
                wa, wb = (tb - t) / (tb - ta), (t - ta) / (tb - ta)
                return (wa * a[0] + wb * b[0], wa * a[1] + wb * b[1])
            a1, a2, a3 = lerp(p0, p1, t0, t1), lerp(p1, p2, t1, t2), lerp(p2, p3, t2, t3)
            b1, b2 = lerp(a1, a2, t0, t2), lerp(a2, a3, t1, t3)
            out.append(lerp(b1, b2, t1, t2))
    return out


def mirror_pts(pts, side):
    return [(side * p[0], p[1]) for p in pts]


def _area(pts):
    return 0.5 * sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))


def ccw(pts):
    return pts if _area(pts) > 0 else pts[::-1]


def offset_closed(pts, d):
    """offset a closed polyline inward by d (d < 0: outward)"""
    is_ccw = _area(pts) > 0
    out = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i - 1], pts[(i + 1) % n]
        tx, ty = _unit((b[0] - a[0], b[1] - a[1]))
        nx, ny = (-ty, tx) if is_ccw else (ty, -tx)        # inward normal
        out.append((pts[i][0] + nx * d, pts[i][1] + ny * d))
    return out


def wing_outline_pts(side, B=BF):
    """dense closed outline (CCW) of the right (+1) or left (-1) wing in the assembled frame"""
    s = B['OVERLAP'] / 2
    pts = [(x - s, y) for (x, y) in cr_closed(B['WING_PTS'], B['SAMPLES'])]
    return ccw(mirror_pts(pts, side))


def point_in_poly(p, poly):
    x, y = p
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i - 1]
        x2, y2 = poly[i]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def dist_to_poly(p, poly):
    best = 1e9
    for i in range(len(poly)):
        a, b = poly[i - 1], poly[i]
        vx, vy = b[0] - a[0], b[1] - a[1]
        L2 = vx * vx + vy * vy
        u = max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L2)) if L2 else 0.0
        best = min(best, math.hypot(p[0] - a[0] - u * vx, p[1] - a[1] - u * vy))
    return best


def x_hits(poly, y):
    """sorted x of the polygon crossings with the horizontal line y"""
    xs = []
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i - 1], poly[i]
        if (y1 > y) != (y2 > y):
            xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
    return sorted(xs)


def lens_x(y, B=BF):
    """x range of the overlap lens at height y: (right wing root edge, left wing root edge)"""
    return x_hits(wing_outline_pts(+1, B), y)[0], x_hits(wing_outline_pts(-1, B), y)[-1]


def heart_pts(c, w, n=28):
    """closed heart (point down), width w, centred on c"""
    s = w / 32.0
    pts = []
    for i in range(n):
        t = 2 * math.pi * (i + 0.5) / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((c[0] + x * s, c[1] + (y + 2.5) * s))
    return ccw(pts)


def heart_windows(B=BF):
    """[(centre, width, has_tab)]: 2 tab hearts straddling the slot back wall + the snap heart"""
    out = []
    for y in B['HEART_TABS']:
        xb = lens_x(y, B)[0] - B['CLR']             # slot back wall
        out.append(((xb + B['HEART_TAB_IN'], y), B['HEART_W'], True))
    x0, x1 = lens_x(B['GEM_Y'], B)
    out.append((((x0 + x1) / 2, B['GEM_Y']), B['GEM_HEART_W'], False))
    return out


def inscribed(c, w):
    """largest circle inside the heart window (centre, radius) - grid search"""
    h = heart_pts(c, w)
    best = (0.0, c)
    for i in range(-20, 21):
        for j in range(-30, 21):
            p = (c[0] + i * w / 100.0, c[1] + j * w / 100.0)
            if point_in_poly(p, h):
                d = dist_to_poly(p, h)
                if d > best[0]:
                    best = (d, p)
    return best[1], best[0]


def tab_discs(B=BF):
    """support tabs under the tab hearts: discs on the inscribed circle, TAB_INSET inside the window
    (the window is the straight-pull shut-off; a disc avoids the heart cusp)"""
    out = []
    for (c, w, tab) in heart_windows(B):
        if tab:
            p, r = inscribed(c, w)
            out.append((p, r - B['TAB_INSET']))
    return out


def gem(B=BF):
    """jewel on the tongue: (centre, r_bottom, r_top). Centre = largest inscribed circle of the
    snap heart; radius at the lip underside = inscribed radius - GEM_CLR (45 deg flanks)."""
    c, w = [(c, w) for (c, w, tab) in heart_windows(B) if not tab][0]
    best = inscribed(c, w)[::-1]
    r_lip = best[0] - B['GEM_CLR']
    r0 = r_lip + (B['LIP_Z0'] - B['TONGUE_T'])
    return best[1], r0, r0 - B['GEM_H']


def gem_centre(B=BF):
    return gem(B)[0]


def _runs(pts, keep, closed):
    n = len(pts)
    if all(keep):
        return [list(pts) + ([pts[0]] if closed else [])]
    start = next(i for i in range(n) if not keep[i]) if closed else -1
    runs, cur = [], []
    for k in range(1, n + 1):
        i = (start + k) % n
        if keep[i]:
            cur.append(pts[i])
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return [r for r in runs if len(r) >= 4]


def deco_keep(p, side, B=BF):
    """decoration point allowed: away from the other wing's footprint (symmetric trim)"""
    other = wing_outline_pts(-side, B)
    return not point_in_poly(p, other) and dist_to_poly(p, other) >= B['TRIM']


def border_runs(side, B=BF):
    off = offset_closed(wing_outline_pts(side, B), B['BORDER_OFF'])[::2]
    return _runs(off, [deco_keep(p, side, B) for p in off], True)


def vein_pts(side, B=BF):
    s = B['OVERLAP'] / 2
    return [mirror_pts([(x - s, y) for (x, y) in v], side) for v in B['VEINS']]


def pearl_pts(side, B=BF):
    """scroll-end pearls + pearls strung along the border bead every BORDER_PEARL_PITCH"""
    s = B['OVERLAP'] / 2
    out = [(side * (x - s), y, r) for (x, y, r) in B['PEARLS']]
    for run in border_runs(side, B):
        acc, nxt = 0.0, B['BORDER_PEARL_PITCH'] / 2
        for a, b in zip(run, run[1:]):
            d = math.hypot(b[0] - a[0], b[1] - a[1])
            while acc + d >= nxt:
                u = (nxt - acc) / d
                out.append((a[0] + u * (b[0] - a[0]), a[1] + u * (b[1] - a[1]), B['BORDER_PEARL_R']))
                nxt += B['BORDER_PEARL_PITCH']
            acc += d
    return out


def boss_pos(side, B=BF):
    return mirror_pts(B['BOSS_POS'], side)


def check_princess(B=BF):
    """layout sanity checks (pure python). Returns dict name -> (ok, detail)."""
    res = {}
    R, L = wing_outline_pts(+1, B), wing_outline_pts(-1, B)
    # overlap lens
    ys = [y / 10.0 for y in range(-160, 160)]
    lens = [(y,) + lens_x(y, B) for y in ys if len(x_hits(R, y)) and len(x_hits(L, y))]
    lens = [l for l in lens if l[2] > l[1]]
    res['lens (y range, max width)'] = (True, (round(lens[0][0], 1), round(lens[-1][0], 1),
                                               round(max(l[2] - l[1] for l in lens), 2)))
    # hearts: tab hearts straddle the back wall, snap heart inside the lens with margin
    for (c, w, tab) in heart_windows(B):
        hp = heart_pts(c, w)
        if tab:
            p, r = inscribed(c, w)
            xb = lens_x(p[1], B)[0] - B['CLR']
            r -= B['TAB_INSET']
            res['tab y=%.1f: into band / under slot' % c[1]] = (xb - (p[0] - r) > 0.25 and p[0] + r - xb > 0.6,
                                                               (round(xb - (p[0] - r), 2), round(p[0] + r - xb, 2)))
        else:
            m = min(min(p[0] - lens_x(p[1], B)[0], lens_x(p[1], B)[1] - p[0]) for p in hp)
            res['snap heart inside lens'] = (m >= 0.6, round(m, 2))
            gm = min(min(c[0] - lens_x(c[1], B)[0], lens_x(c[1], B)[1] - B['CLR'] - c[0]),
                     dist_to_poly(c, R))
            res['jewel margin on tongue'] = (gm >= gem(B)[1] + 0.5, round(gm, 2))
            res['jewel r bottom / top'] = (gem(B)[2] > 0.3, (round(gem(B)[1], 3), round(gem(B)[2], 3)))
    # bosses inside the wing
    m = min(dist_to_poly(p, R) for p in boss_pos(+1, B))
    res['boss margin'] = (m >= B['BOSS_D'] / 2 + 1.0, round(m, 2))
    # decoration inside the outline, clear of the joint
    deco = [q for v in vein_pts(+1, B) for q in v] + [(x, y) for (x, y, r) in pearl_pts(+1, B)]
    m = min(dist_to_poly(p, R) if point_in_poly(p, R) else -1 for p in deco)
    res['deco inside outline'] = (m >= 1.2, round(m, 2))
    bad = [p for p in deco if not deco_keep(p, +1, B)]
    res['deco clear of the joint'] = (not bad, len(bad))
    xs, ys2 = [p[0] for p in R], [p[1] for p in R]
    res['wing size'] = (True, (round(max(xs) - min(xs), 2), round(max(ys2) - min(ys2), 2)))
    res['butterfly span'] = (True, round(2 * max(xs), 2))
    return res


# =====================================================================================
# RHINO BUILD
# =====================================================================================
if RHINO:
    doc = Rhino.RhinoDoc.ActiveDoc
    TOL = max(doc.ModelAbsoluteTolerance, 0.001)
    ATOL = doc.ModelAngleToleranceRadians
    LOG = []
    DEBUG = []

    def log(msg):
        LOG.append(msg)
        print(msg)

    def blist(items):
        l = List[rg.Brep]()
        for b in items:
            if b is not None:
                l.Add(b)
        return l

    def _vol(b):
        try:
            return abs(b.GetVolume())
        except Exception:
            return 0.0

    def one(res, what, fallback):
        if res is None or len(res) == 0:
            log("  !! %s failed - kept previous shape (see _Debug layer)" % what)
            return None
        if len(res) > 1:
            j = rg.Brep.JoinBreps(blist(res), TOL)
            if j is not None and len(j) == 1:
                return j[0]
            log("  .. %s gave %d pieces, keeping the largest" % (what, len(res)))
            return sorted(res, key=_vol)[-1]
        return res[0]

    def union(items, what):
        items = [b for b in items if b is not None]
        if len(items) == 1:
            return items[0]
        r = one(rg.Brep.CreateBooleanUnion(blist(items), TOL), "union " + what, items[0])
        if r is None:
            DEBUG.extend(items[1:])
            return items[0]
        return r

    def diff(a, cutters, what):
        for i, c in enumerate(cutters):
            r = one(rg.Brep.CreateBooleanDifference(a, c, TOL), "difference %s #%d" % (what, i), a)
            if r is None:
                DEBUG.append(c)
            else:
                a = r
        return a

    def inter(a, b, what):
        r = one(rg.Brep.CreateBooleanIntersection(a, b, TOL), "intersection " + what, a)
        if r is None:
            DEBUG.append(b)
            return a
        return r

    # ---------- curves from segment lists ----------
    def to_pt(p, plane):
        if plane == "XZ":
            return rg.Point3d(p[0], 0.0, p[1])
        if plane == "YZ":
            return rg.Point3d(0.0, p[0], p[1])
        return rg.Point3d(p[0], p[1], 0.0)

    def seg_curves(segs, plane="XZ"):
        out = []
        for s in segs:
            if s[0] == 'L':
                c = rg.LineCurve(to_pt(s[1], plane), to_pt(s[2], plane))
            else:
                c = rg.ArcCurve(rg.Arc(to_pt(s[1], plane), to_pt(s[2], plane), to_pt(s[3], plane)))
            if c.GetLength() > 1e-6:
                out.append(c)
        return out

    def solidify(b, what):
        if b is None:
            log("  !! %s: no brep" % what)
            return None
        if b.SolidOrientation == rg.BrepSolidOrientation.Inward:
            b.Flip()
        if not b.IsSolid:
            log("  .. %s is not a closed solid" % what)
        return b

    def revolve(segs, what, origin=(0.0, 0.0, 0.0)):
        """revolve (r, z) segments 360 deg around the Z axis through origin; segments on the axis skipped"""
        axis = rg.Line(rg.Point3d(0, 0, -1000), rg.Point3d(0, 0, 1000))
        faces = []
        for c in seg_curves(segs, "XZ"):
            if abs(c.PointAtStart.X) < 1e-9 and abs(c.PointAtEnd.X) < 1e-9:
                continue
            rs = rg.RevSurface.Create(c, axis, 0.0, 2.0 * math.pi)
            faces.append(rg.Brep.CreateFromRevSurface(rs, False, False))
        j = rg.Brep.JoinBreps(blist(faces), TOL)
        b = solidify(j[0] if j is not None and len(j) else None, what)
        if b is not None:   # move the revolve seam off the XZ / YZ planes (section cuts, parting planes)
            b.Transform(rg.Transform.Rotation(math.radians(45.0), rg.Vector3d.ZAxis, rg.Point3d.Origin))
        if b is not None and any(abs(v) > 0 for v in origin):
            b.Transform(rg.Transform.Translation(origin[0], origin[1], origin[2]))
        return b

    def extrude_closed(segs, plane, vec, what):
        crvs = seg_curves(segs, plane)
        cl = List[rg.Curve]()
        for c in crvs:
            cl.Add(c)
        joined = rg.Curve.JoinCurves(cl, TOL)
        crv = joined[0]
        if not crv.IsClosed:
            log("  !! %s outline not closed" % what)
        srf = rg.Surface.CreateExtrusion(crv, vec)
        b = srf.ToBrep()
        b.Faces.SplitKinkyFaces(Rhino.RhinoMath.DefaultAngleTolerance, True)
        b = b.CapPlanarHoles(TOL)
        return solidify(b, what)

    def extrude_curve(crv, z0, h, what):
        c = crv.DuplicateCurve()
        c.Translate(rg.Vector3d(0, 0, z0 - c.PointAtStart.Z))
        srf = rg.Surface.CreateExtrusion(c, rg.Vector3d(0, 0, h))
        b = srf.ToBrep()
        b.Faces.SplitKinkyFaces(Rhino.RhinoMath.DefaultAngleTolerance, True)
        b = b.CapPlanarHoles(TOL)
        return solidify(b, what)

    def box(x0, x1, y0, y1, z0, z1):
        return rg.Box(rg.BoundingBox(min(x0, x1), min(y0, y1), min(z0, z1),
                                     max(x0, x1), max(y0, y1), max(z0, z1))).ToBrep()

    def cyl(x, y, z0, r, h):
        return rg.Cylinder(rg.Circle(rg.Plane(rg.Point3d(x, y, z0), rg.Vector3d.ZAxis), r), h).ToBrep(True, True)

    def fillet_edges(b, pred, radius, what):
        idx, rad = List[int](), List[float]()
        for e in b.Edges:
            if pred(e):
                idx.Add(e.EdgeIndex)
                rad.Add(radius)
        if idx.Count == 0:
            log("  .. fillet %s: no edges found" % what)
            return b
        try:
            res = rg.Brep.CreateFilletEdges(b, idx, rad, rad, rg.BlendType.Fillet,
                                            rg.RailType.RollingBall, TOL)
        except Exception as ex:
            log("  !! fillet %s raised %s" % (what, ex))
            return b
        if res is None or len(res) == 0:
            log("  !! fillet %s failed - left sharp" % what)
            return b
        return solidify(res[0], what)

    def edge_at_z(z, tol=0.01):
        def pred(e):
            for p in (e.PointAtStart, e.PointAtEnd, e.PointAt(e.Domain.Mid)):
                if abs(p.Z - z) > tol:
                    return False
            return True
        return pred

    def xf(b, t):
        c = b.DuplicateBrep()
        c.Transform(t)
        return c

    MIRROR_X = rg.Transform.Mirror(rg.Plane.WorldYZ)

    # ---------- egg ----------
    def build_egg_halves():
        E = EGG
        log("Egg: base shell")
        base = diff(revolve(egg_base_outer(), "base outer"), [revolve(egg_base_inner(), "base inner")], "base shell")
        zr = E['Z_SEAM'] + E['SNAP_DZ']
        tor = rg.Torus(rg.Plane(rg.Point3d(0, 0, zr), rg.Vector3d.ZAxis),
                       E['NECK_R'] + E['GROOVE_R'] - E['GROOVE_DEPTH'], E['GROOVE_R'])
        groove = solidify(rg.Brep.CreateFromSurface(tor.ToNurbsSurface()), "groove torus")
        base = diff(base, [groove], "neck snap groove")
        log("Egg: cap shell")
        cap = diff(revolve(egg_cap_outer(), "cap outer"), [revolve(egg_cap_inner(), "cap inner")], "cap shell")
        cap = union([cap, revolve(egg_snap_rib(), "snap rib")], "cap snap rib")
        pb, pc, pad_b, pad_c = hinge_attach()
        w = E['H_W'] / 2
        base = union([base, box(pad_b[0], pad_b[1], -w, w, pad_b[2], pad_b[3])], "base hinge pad")
        cap = union([cap, box(pad_c[0], pad_c[1], -w, w, pad_c[2], pad_c[3])], "cap hinge pad")
        return base, cap

    def egg_state(base, cap, theta):
        E = EGG
        hx, hz = hinge_pivot()
        rot = rg.Transform.Rotation(math.radians(theta), rg.Vector3d(0, -1, 0), rg.Point3d(hx, 0, hz))
        cap_t = xf(cap, rot)
        strap = extrude_closed(hinge_strap(theta), "XZ", rg.Vector3d(0, E['H_W'], 0), "hinge strap")
        strap.Transform(rg.Transform.Translation(0, -E['H_W'] / 2, 0))
        if theta > 0:   # cap clear of the base: one moulded part (base + living hinge + cap)
            return [("shell", union([base, cap_t, strap], "egg + hinge (%g deg)" % theta))]
        # closed: cap sits on the lip and the snap rib bites into the groove -> keep 2 solids
        return [("base+hinge", union([base, strap], "base + hinge")), ("cap", cap_t)]

    # ---------- princess butterfly v3 ----------
    def pts3(pts2d, z):
        l = List[rg.Point3d]()
        for (x, y) in pts2d:
            l.Add(rg.Point3d(x, y, z))
        return l

    def interp(pts2d, z, closed=False):
        if closed:
            return rg.Curve.CreateInterpolatedCurve(pts3(pts2d, z), 3, rg.CurveKnotStyle.ChordPeriodic)
        return rg.Curve.CreateInterpolatedCurve(pts3(pts2d, z), 3)

    def prism(pts2d, z0, z1, what):
        """vertical extrusion of a closed outline (dense point list -> periodic NURBS)"""
        return extrude_curve(interp(pts2d, z0, closed=True), z0, z1 - z0, what)

    def pipe(crv, r, what):
        res = rg.Brep.CreatePipe(crv, r, False, rg.PipeCapMode.Round, True, TOL, ATOL)
        if res is None or len(res) == 0:
            log("  !! pipe %s failed" % what)
            return None
        return solidify(res[0], what)

    def sharp_edges_at_z(z, near, min_deg=30.0, tol=0.01):
        """edges lying at height z, with their midpoint accepted by near(x, y), whose two faces meet
        at > min_deg (skips tangent fillet seams)"""
        cmin = math.cos(math.radians(min_deg))

        def pred(e):
            if not edge_at_z(z, tol)(e):
                return False
            m = e.PointAt(e.Domain.Mid)
            if not near(m.X, m.Y):
                return False
            fi = e.AdjacentFaces()
            if fi is None or len(fi) != 2:
                return False
            mid = e.PointAt(e.Domain.Mid)
            ns = []
            for i in fi:
                f = e.Brep.Faces[i]
                ok, u, v = f.ClosestPoint(mid)
                if not ok:
                    return False
                ns.append(f.NormalAt(u, v))
            return abs(ns[0] * ns[1]) < cmin
        return pred

    def wing(side):
        """side +1: P1 right wing (MALE: thin tongue + jewel), -1: P2 left wing (FEMALE: thick band,
        slot under the lip, heart windows + tabs). Both plates z 0..T in the assembled frame."""
        B = BF
        t = B['T']
        own, other = wing_outline_pts(side), wing_outline_pts(-side)
        log("Butterfly: %s wing" % ("P1 right (male)" if side > 0 else "P2 left (female)"))
        plate = prism(own, 0.0, t, "wing plate")
        plate = fillet_edges(plate, edge_at_z(t), B['FILLET_TOP'], "wing rim top")
        plate = fillet_edges(plate, edge_at_z(0.0), B['FILLET_BOT'], "wing rim bottom")
        adds = [plate]
        # raised decoration (half-round beads + pearls) for the UV colour-change coating
        for run in border_runs(side):
            adds.append(pipe(interp(run, t), B['DECO_R'], "border bead"))
        for v in vein_pts(side):
            adds.append(pipe(interp(v, t), B['DECO_R'], "vein scroll"))
        for (x, y, r) in pearl_pts(side):
            adds.append(rg.Sphere(rg.Point3d(x, y, t - 0.1), r).ToBrep())
        # clip bosses (1 deg draft, narrow at the free end)
        bh = B['BOSS_H'] + 0.2
        r_top = B['BOSS_D'] / 2
        r_bot = r_top - bh * math.tan(math.radians(B['BOSS_DRAFT']))
        for (x, y) in boss_pos(side):
            adds.append(revolve(pin_profile(r_bot, r_top, bh), "clip boss", (x, y, -B['BOSS_H'])))
        cuts = [revolve(hole_profile(B['CLIP_HOLE_D'] / 2, B['CLIP_HOLE_DEPTH']), "clip hole",
                        (x, y, -B['BOSS_H'])) for (x, y) in boss_pos(side)]
        if side < 0:
            # FEMALE: thicker band behind the slot (right wing root edge + THICK_BAND, inside own rim)
            band = inter(prism(offset_closed(other, -B['THICK_BAND']), B['THICK_Z0'], 0.5, "band A"),
                         prism(offset_closed(own, B['THICK_INSET']), B['THICK_Z0'] - 1, 1.0, "band B"),
                         "thick root band")
            adds.append(band)
            part = union(adds, "left wing + band + decoration")
            # side slot = right wing footprint + CLR, from below up to the lip underside
            slot = prism(offset_closed(other, -B['CLR']), B['THICK_Z0'] - 0.3, B['LIP_Z0'], "slot")
            part = diff(part, cuts + [slot], "clip holes / slot")
            hearts = heart_windows()
            tabs = [cyl(p[0], p[1], B['TAB_Z0'], r, 0.5 - B['TAB_Z0']) for (p, r) in tab_discs()]
            part = union([part] + tabs, "support tabs")
            wins = [prism(heart_pts(c, w), B['FLOOR_Z'], t + 1.0, "heart window") for (c, w, tab) in hearts]
            part = diff(part, wins, "heart windows")
        else:
            # MALE: everything above TONGUE_T inside the left wing footprint (+CLR) is removed
            part = union(adds, "right wing + decoration")
            step = prism(offset_closed(other, -B['CLR']), B['TONGUE_T'], t + 1.0, "tongue step")
            part = diff(part, cuts + [step], "clip holes / tongue")
            g, r0, r1 = gem()
            jewel = revolve(pin_profile(r0 + EPS, r1, B['GEM_H'] + EPS, 0.0, 0.0),
                            "jewel", (g[0], g[1], B['TONGUE_T'] - EPS))
            part = union([part, jewel], "tongue jewel")
        # soften the sharp top edges of the tongue step / heart windows (not the decoration roots)
        hw = heart_windows()

        def near_joint(x, y):
            if dist_to_poly((x, y), other) < B['CLR'] + 0.3:
                return True
            return any(math.hypot(x - c[0], y - c[1]) < w for (c, w, tab) in hw) if side < 0 else False
        part = fillet_edges(part, sharp_edges_at_z(t, near_joint), B['EDGE_SOFT'], "window / step top edges")
        return part

    def clip_part():
        B = BF
        log("Butterfly: clip")
        c = extrude_closed(clip_outline(), "YZ", rg.Vector3d(B['CLIP_W'], 0, 0), "clip profile")
        pins = [revolve(pin_profile(B['CLIP_PIN_D'] / 2, B['CLIP_PIN_D'] / 2, B['CLIP_PIN_H'] + 0.1, 0.35),
                        "clip pin", (B['CLIP_W'] / 2, y, -0.1)) for y in B['CLIP_PIN_Y']]
        return union([c] + pins, "clip pins")

    def clip_on_wing(c, side):
        B = BF
        x, y = boss_pos(side)[0]
        return xf(c, rg.Transform.Translation(x - B['CLIP_W'] / 2, y - B['CLIP_PIN_Y'][0], -B['BOSS_H']))

    def pack_in_egg(parts):
        """packing inside the closed capsule (positions found and verified by ../verify_princess.py)"""
        out = []
        for key, tr in PACK:
            b = xf(parts[key], rg.Transform.Rotation(math.radians(tr[0]), rg.Vector3d.XAxis, rg.Point3d.Origin))
            b.Transform(rg.Transform.Rotation(math.radians(tr[1]), rg.Vector3d.ZAxis, rg.Point3d.Origin))
            b.Transform(rg.Transform.Translation(tr[2], tr[3], tr[4]))
            out.append(b)
        return out

    # ---------- document ----------
    ROOT = "KinderToy"

    def layer(name, rgb):
        full = ROOT + "::" + name
        idx = doc.Layers.FindByFullPath(full, -1)
        if idx < 0:
            parent = doc.Layers.FindByFullPath(ROOT, -1)
            if parent < 0:
                pl = Rhino.DocObjects.Layer()
                pl.Name = ROOT
                parent = doc.Layers.Add(pl)
            l = Rhino.DocObjects.Layer()
            l.Name = name
            l.ParentLayerId = doc.Layers[parent].Id
            l.Color = System.Drawing.Color.FromArgb(rgb[0], rgb[1], rgb[2])
            idx = doc.Layers.Add(l)
        return idx

    def clear_previous():
        root = doc.Layers.FindByFullPath(ROOT, -1)
        if root < 0:
            return
        n = 0
        for l in doc.Layers:
            if l.FullPath == ROOT or l.FullPath.startswith(ROOT + "::"):
                for o in doc.Objects.FindByLayer(l) or []:
                    doc.Objects.Delete(o, True)
                    n += 1
        if n:
            log("removed %d objects of a previous run" % n)

    SCALE = rg.Transform.Scale(rg.Point3d.Origin,
                               Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem))

    def add(b, lay, name, offset=(0, 0, 0), info=None):
        if b is None:
            return
        c = xf(b, rg.Transform.Translation(offset[0], offset[1], offset[2]))
        c.Transform(SCALE)
        a = Rhino.DocObjects.ObjectAttributes()
        a.LayerIndex = lay
        a.Name = name
        a.SetUserString("generator", "kinder_rhino_build.py")
        for k, v in (info or {}).items():
            a.SetUserString(k, str(v))
        doc.Objects.AddBrep(c, a)

    def main():
        if doc.ModelUnitSystem != Rhino.UnitSystem.Millimeters:
            log("Document units are %s - geometry is scaled from mm." % doc.ModelUnitSystem)
        clear_previous()
        E, B = EGG, BF

        base, cap = build_egg_halves()
        einfo = dict(L_total=E['L_TOTAL'], wall=E['T'], seam=E['Z_SEAM'])
        for i, (name, th) in enumerate(E['STATES']):
            log("Egg state %s (%g deg)" % (name, th))
            lay = layer(name, (255, 160, 30))
            for sub, egg in egg_state(base, cap, th):
                add(egg, lay, name + "_" + sub, (0, i * E['STATE_DY'], 0), dict(einfo, open_deg=th))
                if th == 0:
                    log("Egg: closed section (%s)" % sub)
                    sect = diff(egg, [box(-60, 60, -40, 0, -10, 60)], "section cut")  # Front view looks inside
                    add(sect, layer("Egg_Closed_Section", (255, 200, 120)), "Egg_Closed_Section_" + sub,
                        (0, -E['STATE_DY'], 0))

        parts = {'R': wing(+1), 'L': wing(-1), 'C': clip_part()}
        ax, ay, az = B['ASM_OFFSET']
        la = layer("Butterfly_Assembly", (245, 120, 180))
        add(parts['L'], la, "P2_wing_L (female)", (ax, ay, az))
        add(parts['R'], la, "P1_wing_R (male)", (ax, ay, az))
        add(clip_on_wing(parts['C'], -1), la, "P3_clip_L", (ax, ay, az))
        add(clip_on_wing(parts['C'], +1), la, "P3_clip_R", (ax, ay, az))
        lp = layer("Butterfly_Parts", (120, 160, 245))
        ox, oy, oz = B['PARTS_OFFSET']
        uv = "ABS + UV colour-change coating"
        add(parts['R'], lp, "P1_wing_R (male)", (ox, oy, oz), dict(material=uv))
        add(parts['L'], lp, "P2_wing_L (female)", (ox + 50, oy, oz), dict(material=uv))
        add(parts['C'], lp, "P3_clip (x2)", (ox + 75, oy - 12, oz), dict(material="ABS", qty=2))
        lk = layer("Packed_In_Egg", (240, 80, 150))
        for (key, _), b in zip(PACK, pack_in_egg(parts)):
            add(b, lk, "packed_" + key)
            add(b, lk, "packed_" + key + "_section", (0, -E['STATE_DY'], 0))
        if DEBUG:
            ld = layer("_Debug", (255, 0, 0))
            for b in DEBUG:
                add(b, ld, "failed boolean operand")
        doc.Views.Redraw()
        fails = [m for m in LOG if m.strip().startswith("!!")]
        print("---- done: %d warnings%s" % (len(fails), "" if not fails else " (see above)"))

    if __name__ == "__main__":
        main()
