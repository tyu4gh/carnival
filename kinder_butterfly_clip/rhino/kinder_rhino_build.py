# -*- coding: utf-8 -*-
"""
Kinder Surprise capsule + "Fairytale Princess" butterfly hair clip, built from scratch with RhinoCommon.

How to run (Rhino 7 / 8 / 9 WIP, Windows or Mac):
    Rhino command line  ->  RunPythonScript  ->  pick this file
    or ScriptEditor -> open this file -> Run (IronPython 2 or CPython 3 both work)

Everything is parametric: edit EGG / BF below and run again.
Objects created by a previous run (layer tree "KinderToy") are deleted first.

Toy v5 (4 parts, injection moulded ABS, no metal, no surface patterns). Wing shape from the
user's model buttclip_Ver.1.1.3dm; both wings are thin organic sections (thinner, slightly
drooping towards the tips); the overlap at the centre is only ~2 mm:
    P1 right wing  - one continuous gentle arc that dips towards the centre, thins out to 0.8 mm
                     and ends in a small round bar (D 1.4)
    P2 left wing   - its root edge curls down into a small hook ("LEGO hand") that holds the bar
                     (hook bore along Y: one side core in the left-wing tool, like a LEGO hand)
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
# PARAMETERS - "FAIRYTALE PRINCESS" BUTTERFLY HAIR CLIP v5  (4 parts, ABS, no metal)
# assembled frame: X = span (right wing +X), Y = up the head, Z = up.
# Wing shape = the user's model buttclip_Ver.1.1.3dm (layer "wing right", mirrored for the left).
# Both wings are thin, organic sections (thinner and slightly drooping towards the tips):
#   P2 left wing  : its root edge curls down into a small "hand" (C-hook) that holds the bar
#   P1 right wing : one continuous gentle arc that dips towards the centre, thins out, and ends in
#                   a small round bar lying in the left wing's hand (like the user's sketch)
# =====================================================================================
BF = dict(
    # right-wing outline, through-points (user model, root edge at x = 0.25, centre gap 0.5 mm)
    WING_PTS=[(0.25, -0.74), (0.84, -4.09), (2.45, -7.1), (4.67, -9.71), (7.35, -11.83),
              (10.31, -13.56), (13.45, -14.91), (16.81, -15.4), (19.38, -13.39), (19.56, -10.0),
              (18.57, -6.73), (18.22, -3.51), (20.58, -1.04), (22.46, 1.82), (23.83, 4.96),
              (24.83, 8.23), (25.15, 11.63), (23.85, 14.73), (20.6, 15.42), (17.27, 14.65),
              (14.06, 13.45), (11.02, 11.87), (8.21, 9.91), (5.62, 7.68), (3.21, 5.23), (1.13, 2.52)],
    SAMPLES=6,                   # Catmull-Rom samples per span (dense outline used everywhere)
    OVERLAP=5.0,                 # each wing slides OVERLAP/2 towards the centre
    # ---- organic sections (both wings)
    T=1.4,                       # body thickness
    T_TIP=1.0,                   # thickness at the outer tips
    DROOP=0.4,                   # the outer part of each wing curves down by this much
    DROOP_FROM=14.0,             # |x| where thinning / drooping towards the tip starts
    TIP_X=23.0,                  # |x| where it ends
    RIM_R=0.35,                  # rounded rim (limited by the thin end of the right wing)
    # ---- right wing arc: from the bar up to full height
    T_END=0.8,                   # thickness where it meets the bar
    ARC_LEN=11.0,                # length of the rising arc (cubic Hermite, flat at its top)
    ARC_SLOPE=0.22,              # slope at the bar (about 12 deg)
    # ---- bar on the right wing's root edge
    ROD_LEN=7.0,                 # straight, round-section part of the root edge
    ROD_R=0.7,                   # bar radius (diameter 1.4)
    ROD_IN=0.15,                 # bar sticks out this much past the plate end
    BAR_GAP=0.1,                 # bar top below the left wing's underside
    SOFT_K=1.2,                  # smoothing of the corners where a straight root edge meets the curve
    # ---- left wing hand (C-hook at the root edge, constant section along Y, rounded ends)
    JAW_COVER=1.15,              # left wing's straight root edge is this far right of the bar axis
    GRIP=0.02,                   # bore radius = ROD_R - GRIP (light friction grip)
    HAND_WALL=0.5,               # hook wall
    LIP_ANG=50.0,                # lip tip angle below horizontal (sets the snap: see check)
    HAND_BLEND=0.8,              # concave blend radius between the hook and the wing underside
    HAND_END_CLR=0.5,            # hand is this much shorter than the bar at each end
    HAND_END_R=1.2,              # rounded ends of the hand in plan view
    # ---- clip interface (same one-piece ABS clip)
    BOSS_D=5.0, BOSS_H=1.5, BOSS_DRAFT=1.0,
    CLIP_PIN_D=2.25, CLIP_HOLE_D=2.20, CLIP_PIN_H=2.1, CLIP_HOLE_DEPTH=2.3,
    BOSS_POS=[(11.5, -11.25), (11.5, 2.75)],   # right wing, assembled frame; mirrored for the left
    CLIP_W=7.0, CLIP_L=22.0, CLIP_T=1.4, CLIP_PIN_Y=[4.0, 18.0],
    ASM_OFFSET=(110.0, 0.0, 0.0),
    PARTS_OFFSET=(170.0, 0.0, 0.0),
)

# packing in the closed capsule: part, (rot about X deg, rot about Z deg, dx, dy, dz) applied to
# the part's assembled-frame geometry; found and verified (no clash with the real shell) by
# ../verify_princess.py
PACK = [("R", (90, 0, -10.835, -1.940, 22.689)),
        ("L", (90, 0, 11.065, 1.360, 22.689)),
        ("C", (90, 0, -3.500, 5.840, 11.810)),
        ("C", (90, 180, 3.500, -5.840, 11.810))]

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


# ---------------- princess butterfly v5 maths (plain python, no numpy) ----------------
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


def arc_chain(pts, closed=True):
    """smooth outline as circular arcs through point triples (lines where collinear). Fallback for
    Rhino when a spline outline will not extrude: same arc/line pipeline as the clip and hinge."""
    n = len(pts)
    seq = list(pts) + ([pts[0]] if closed else [])
    if (len(seq) - 1) % 2:
        seq = seq[:-2] + [seq[-1]] if not closed else list(pts[:-1]) + [pts[0]]
    segs = []
    for i in range(0, len(seq) - 2, 2):
        a, m, b = seq[i], seq[i + 1], seq[i + 2]
        cross = (m[0] - a[0]) * (b[1] - a[1]) - (m[1] - a[1]) * (b[0] - a[0])
        if abs(cross) < 1e-6 * max(1e-9, math.hypot(b[0] - a[0], b[1] - a[1])) ** 2:
            segs.append(('L', a, b))
        else:
            segs.append(('A', a, m, b))
    if len(seq) % 2 == 0:                     # one point left over
        segs.append(('L', seq[-2], seq[-1]))
    return segs


def wing_outline_pts(side, B=BF):
    """dense closed outline (CCW) of the user's wing, right (+1) or left (-1), assembled frame"""
    s = B['OVERLAP'] / 2
    pts = [(x - s, y) for (x, y) in cr_closed(B['WING_PTS'], B['SAMPLES'])]
    return ccw(mirror_pts(pts, side))


def x_hits(poly, y):
    """sorted x of the polygon crossings with the horizontal line y"""
    xs = []
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i - 1], poly[i]
        if (y1 > y) != (y2 > y):
            xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
    return sorted(xs)


def point_in_poly(p, poly):
    return len([x for x in x_hits(poly, p[1]) if x > p[0]]) % 2 == 1


def dist_to_poly(p, poly):
    best = 1e9
    for i in range(len(poly)):
        a, b = poly[i - 1], poly[i]
        vx, vy = b[0] - a[0], b[1] - a[1]
        L2 = vx * vx + vy * vy
        u = max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L2)) if L2 else 0.0
        best = min(best, math.hypot(p[0] - a[0] - u * vx, p[1] - a[1] - u * vy))
    return best


def _root_span(x_cut, B=BF):
    """y-interval where the original right-wing root edge lies left of x_cut"""
    R = wing_outline_pts(+1, B)
    ys = [i / 20.0 for i in range(-300, 301)]
    inside = [y for y in ys if x_hits(R, y) and x_hits(R, y)[0] < x_cut]
    return (min(inside), max(inside)) if inside else (0.0, 0.0)


def rod_line(B=BF):
    """x of the straight root edge, and (y0, y1) of the bar. The edge is moved right until
    ROD_LEN + 2 mm of it is straight (the bar keeps 1 mm away from the rounded corners)."""
    lo, hi = -10.0, 10.0
    for _ in range(50):
        mid = (lo + hi) / 2
        a, b = _root_span(mid, B)
        if b - a < B['ROD_LEN'] + 2.0:
            lo = mid
        else:
            hi = mid
    a, b = _root_span(hi, B)
    c = (a + b) / 2
    return hi, (c - B['ROD_LEN'] / 2, c + B['ROD_LEN'] / 2)


def right_outline_pts(B=BF):
    """right wing outline with a straight root edge (smooth max with x = x_rod)"""
    xr, _ = rod_line(B)
    k = B['SOFT_K']
    out = []
    for (x, y) in wing_outline_pts(+1, B):
        out.append((0.5 * (x + xr + math.sqrt((x - xr) ** 2 + k * k)), y))
    return out


def rod_axis(B=BF):
    """bar axis: (xc, zc, y0, y1)"""
    xr, (y0, y1) = rod_line(B)
    return xr + B['ROD_R'] - B['ROD_IN'], -(B['ROD_R'] + B['BAR_GAP']), y0, y1


def left_root_x(B=BF):
    return rod_axis(B)[0] + B['JAW_COVER']


def left_outline_pts(B=BF):
    """left wing outline with a straight root edge at x = left_root_x (smooth min)"""
    xl = left_root_x(B)
    k = B['SOFT_K']
    return [(0.5 * (x + xl - math.sqrt((x - xl) ** 2 + k * k)), y) for (x, y) in wing_outline_pts(-1, B)]


def _smoother(u):
    u = min(1.0, max(0.0, u))
    return u * u * u * (u * (6 * u - 15) + 10)


def _tip(ax, B=BF):
    """thinning / drooping factor 0..1 towards the outer tip (ax = |x|)"""
    return _smoother((ax - B['DROOP_FROM']) / (B['TIP_X'] - B['DROOP_FROM']))


def right_z(x, B=BF):
    """(z_bottom, z_top) of the right wing at x: arc from the bar up to full height, then the
    gentle droop / thinning towards the tip"""
    xc, zc, _, _ = rod_axis(B)
    zf = B['T'] / 2
    s0 = B['ARC_SLOPE']
    L = B['ARC_LEN']
    u = (x - xc) / L
    if u <= 0:
        mid, t = zc + s0 * (x - xc), B['T_END']
    elif u < 1:
        h00, h10, h01 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2
        mid = h00 * zc + h10 * s0 * L + h01 * zf
        t = B['T_END'] + (B['T'] - B['T_END']) * _smoother(u)
    else:
        mid, t = zf, B['T']
    f = _tip(x, B)
    mid -= B['DROOP'] * f
    t -= (B['T'] - B['T_TIP']) * f
    return mid - t / 2, mid + t / 2


def left_z(x, B=BF):
    """(z_bottom, z_top) of the left wing: flat underside z = 0 near the root, thinning and
    drooping towards the tip"""
    f = _tip(-x, B)
    mid = B['T'] / 2 - B['DROOP'] * f
    t = B['T'] - (B['T'] - B['T_TIP']) * f
    return mid - t / 2, mid + t / 2


def section_pts(fz, x_from=-40.0, x_to=40.0, step=0.5):
    """(top points, bottom points) of a wing's XZ section"""
    n = int(round((x_to - x_from) / step))
    xs = [x_from + i * step for i in range(n + 1)]
    return [(x, fz(x)[1]) for x in xs], [(x, fz(x)[0]) for x in xs]


def hand_profile(B=BF):
    """closed (x, z) section of the left wing's hook ("LEGO hand"), bore along Y, mouth to +X.
    The hook hangs from the wing underside (z = 0) with a concave blend; its top goes 0.3 into
    the plate. Outer ring around the bar, rounded lip tip, bore = bar - GRIP."""
    xc, zc, y0, y1 = rod_axis(B)
    ri = B['ROD_R'] - B['GRIP']
    w = B['HAND_WALL']
    ro = ri + w
    rb = B['HAND_BLEND']
    zl = 0.05                                    # blend line 0.05 inside the plate (no tangency)
    xf = xc - math.sqrt((ro + rb) ** 2 - (zl - rb - zc) ** 2)
    cf = (xf, zl - rb)
    u = _unit((xc - cf[0], zc - cf[1]))
    t1 = (cf[0] + rb * u[0], cf[1] + rb * u[1])
    mb = _unit((u[0], u[1] + 1.0))
    mid_blend = (cf[0] + rb * mb[0], cf[1] + rb * mb[1])
    a1 = math.degrees(math.atan2(t1[1] - zc, t1[0] - xc))
    aL = 360.0 - B['LIP_ANG']

    def P(r, a):
        return (xc + r * math.cos(math.radians(a)), zc + r * math.sin(math.radians(a)))
    po, pi = P(ro, aL), P(ri, aL)
    pm = P((ri + ro) / 2, aL)
    tg = (-math.sin(math.radians(aL)), math.cos(math.radians(aL)))
    cap = (pm[0] + w / 2 * tg[0], pm[1] + w / 2 * tg[1])
    top = (xc, zc + ri)
    return [('A', (xf, zl), mid_blend, t1),
            ('A', t1, P(ro, (a1 + aL) / 2), po),
            ('A', po, cap, pi),
            ('A', pi, P(ri, (aL + 90.0) / 2), top),
            ('L', top, (xc, 0.3)), ('L', (xc, 0.3), (xf, 0.3)), ('L', (xf, 0.3), (xf, zl))]


def hand_span(B=BF):
    xc, zc, y0, y1 = rod_axis(B)
    return y0 + B['HAND_END_CLR'], y1 - B['HAND_END_CLR']


def hand_plan(B=BF, n=16):
    """plan footprint of the hand: stadium with rounded ends (HAND_END_R) around the hook"""
    h0, h1 = hand_span(B)
    xs = [p[1][0] for p in hand_profile(B)] + [p[-1][0] for p in hand_profile(B)]
    x0, x1 = min(xs) - 0.3, max(xs) + 0.3
    r = min(B['HAND_END_R'], (x1 - x0) / 2, (h1 - h0) / 2)
    pts = []
    for (cx, cy, a0) in ((x1 - r, h1 - r, 0), (x0 + r, h1 - r, 90), (x0 + r, h0 + r, 180), (x1 - r, h0 + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90.0 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def boss_pos(side, B=BF):
    return mirror_pts(B['BOSS_POS'], side)


def check_princess(B=BF):
    """layout sanity checks (pure python). Returns dict name -> (ok, detail)."""
    res = {}
    R, L = right_outline_pts(B), left_outline_pts(B)
    xc, zc, y0, y1 = rod_axis(B)
    xr, _ = rod_line(B)
    xl = left_root_x(B)
    # bar + hand under the left wing
    m = min(dist_to_poly((x, y), L) if point_in_poly((x, y), L) else -1
            for y in (y0, (y0 + y1) / 2, y1) for x in (xc - B['ROD_R'], xc + 0.3))
    res['bar under the left wing (margin)'] = (m >= 0.4, round(m, 2))
    # right wing passes under the left wing's root with clearance (left underside z = 0)
    def left_under(x):            # wing underside incl. the rounded rim at the root edge
        z = left_z(x, B)[0]
        e = x - (xl - B['RIM_R'])
        return z + (B['RIM_R'] - math.sqrt(max(0.0, B['RIM_R'] ** 2 - e * e)) if e > 0 else 0.0)
    gaps = [left_under(x) - right_z(x, B)[1] for x in [xc + i * 0.05 for i in range(0, int((xl - xc) / 0.05) + 1)]]
    res['right wing under the left root (min gap)'] = (min(gaps) >= 0.15, round(min(gaps), 3))
    # snap: lip tip inner point to the wing underside vs bar diameter
    ri = B['ROD_R'] - B['GRIP']
    gap = -(zc - ri * math.sin(math.radians(B['LIP_ANG'])))
    d = 2 * B['ROD_R'] - gap
    Lj = (ri + B['HAND_WALL'] / 2) * math.radians(180 - B['LIP_ANG'])
    eps = 1.5 * B['HAND_WALL'] * d / Lj ** 2
    res['snap: lip opening / strain'] = (0 < d < 0.15 and eps < 0.03, (round(d, 3), "%.1f %%" % (eps * 100)))
    # the right wing's neck passes the lip with clearance
    px = xc + ri * math.cos(math.radians(B['LIP_ANG']))
    neck = right_z(px, B)[0] - (zc - ri * math.sin(math.radians(B['LIP_ANG'])))
    res['neck above the lip tip'] = (neck > 0.15, round(neck, 3))
    # hook depth below the wing
    res['hook depth below the wing'] = (True, round(-(zc - ri - B['HAND_WALL']), 2))
    m = min(dist_to_poly(p, R) for p in boss_pos(+1, B))
    res['boss margin to outline'] = (m >= B['BOSS_D'] / 2 + 0.6, round(m, 2))
    bx = min(p[0] for p in boss_pos(+1, B))
    res['clip clear of the right wing underside'] = (right_z(bx - B['CLIP_W'] / 2, B)[0] > -B['BOSS_H'] + 0.25,
                                                     round(right_z(bx - B['CLIP_W'] / 2, B)[0], 2))
    res['boss attaches to the underside'] = (all(right_z(bx + dx, B)[0] < 0.15 for dx in (-2.5, 0, 2.5)), True)
    xs, ys = [p[0] for p in R], [p[1] for p in R]
    res['right wing size'] = (True, (round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2)))
    res['butterfly span'] = (True, round(max(xs) - min(p[0] for p in L), 2))
    res['plan overlap at the centre'] = (True, round(xl - (xc - B['ROD_R']), 2))
    res['bar length / hand length'] = (True, (B['ROD_LEN'], round(hand_span(B)[1] - hand_span(B)[0], 2)))
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
    DEBUG_CRV = []

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
        if items and items[0] is None:
            log("  !! union %s: base solid missing" % what)
        items = [b for b in items if b is not None]
        if not items:
            return None
        if len(items) == 1:
            return items[0]
        res = rg.Brep.CreateBooleanUnion(blist(items), TOL)
        if res is not None and len(res) > 0:
            r = one(res, "union " + what, items[0])
            if r is not None:
                return r
        # bulk union failed: add the pieces one by one, skipping only the ones that fail
        log("  .. union %s: bulk union failed, adding %d pieces one by one" % (what, len(items) - 1))
        acc = items[0]
        for k, b in enumerate(items[1:]):
            r = one(rg.Brep.CreateBooleanUnion(blist([acc, b]), TOL), "union %s piece %d" % (what, k + 1), acc)
            if r is None:
                DEBUG.append(b)
            else:
                acc = r
        return acc

    def diff(a, cutters, what):
        if a is None:
            log("  !! %s: nothing to cut from" % what)
            return None
        for i, c in enumerate(cutters):
            if c is None:
                log("  !! %s #%d: cutter missing, skipped" % (what, i))
                continue
            r = one(rg.Brep.CreateBooleanDifference(a, c, TOL), "difference %s #%d" % (what, i), a)
            if r is None:
                DEBUG.append(c)
            else:
                a = r
        return a

    def inter(a, b, what):
        if a is None or b is None:
            log("  !! intersection %s: operand missing" % what)
            return a if b is None else b
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

    def _closed_solid(b):
        if b is None:
            return None
        if b.SolidOrientation == rg.BrepSolidOrientation.Inward:
            b.Flip()
        return b if b.IsSolid else None

    def describe(c):
        try:
            return "closed=%s periodic=%s planar=%s degree=%d points=%d length=%.2f" % (
                c.IsClosed, c.IsPeriodic, c.IsPlanar(), c.Degree, c.ToNurbsCurve().Points.Count, c.GetLength())
        except Exception as ex:
            return "(describe failed: %s)" % ex

    def extrude_curve(crv, z0, h, what, fallback_segs=None):
        """closed planar curve at height z0 -> capped solid z0..z0+h. Tries Extrusion.Create
        (= ExtrudeCrv), planar face + ExtrudeSrf, side surface + planar caps, a rebuilt curve, and
        finally fallback_segs (arc/line chain, same pipeline as the clip / hinge strap)."""
        tries = []
        c = None
        if crv is not None:
            c = crv.DuplicateCurve()
            c.Translate(rg.Vector3d(0, 0, z0 - c.PointAtStart.Z))
            if not c.IsClosed:
                c.MakeClosed(TOL)

        def m_extrusion(cv):
            ext = rg.Extrusion.Create(cv, h, True)
            if ext is None:
                return None, "Extrusion.Create returned None"
            b = ext.ToBrep(True)
            if b is None:
                return None, "Extrusion.ToBrep returned None"
            if b.GetBoundingBox(True).Max.Z < z0 + h / 2:     # extruded towards -Z
                b.Translate(rg.Vector3d(0, 0, h))
            return b, ""

        def m_face(cv):
            caps = rg.Brep.CreatePlanarBreps(cv, TOL)
            if caps is None or len(caps) == 0:
                return None, "CreatePlanarBreps returned nothing"
            path = rg.LineCurve(rg.Point3d(0, 0, z0), rg.Point3d(0, 0, z0 + h))
            return caps[0].Faces[0].CreateExtrusion(path, True), ""

        def m_caps(cv):
            side = rg.Surface.CreateExtrusion(cv, rg.Vector3d(0, 0, h)).ToBrep()
            top = cv.DuplicateCurve()
            top.Translate(rg.Vector3d(0, 0, h))
            pieces = [side]
            for k in (cv, top):
                caps = rg.Brep.CreatePlanarBreps(k, TOL)
                if caps is None or len(caps) == 0:
                    return None, "CreatePlanarBreps returned nothing"
                pieces.extend(caps)
            j = rg.Brep.JoinBreps(blist(pieces), TOL)
            if j is None or len(j) != 1:
                return None, "JoinBreps gave %s pieces" % (0 if j is None else len(j))
            return j[0], ""

        methods = []
        if c is not None:
            methods = [("Extrusion.Create", m_extrusion, lambda: c), ("planar face + ExtrudeSrf", m_face, lambda: c),
                       ("surface + planar caps", m_caps, lambda: c),
                       ("rebuilt curve", m_extrusion, lambda: c.Rebuild(80, 3, True))]
        for name, fn, get in methods:
            try:
                b, why = fn(get())
                if b is not None:
                    if b.SolidOrientation == rg.BrepSolidOrientation.Inward:
                        b.Flip()
                    if b.IsSolid:
                        return b
                    why = "result not closed (%d naked edges)" % sum(
                        1 for e in b.Edges if e.Valence == rg.EdgeAdjacency.Naked)
            except Exception as ex:
                why = "raised %s: %s" % (type(ex).__name__, ex)
            tries.append("%s: %s" % (name, why))
        if fallback_segs is not None:
            try:
                b = extrude_closed(fallback_segs, "XY", rg.Vector3d(0, 0, h), what + " (arc chain)")
                if b is not None:
                    b.Translate(rg.Vector3d(0, 0, z0))
                    if b.IsSolid:
                        if tries:
                            log("  .. %s: spline outline would not extrude, used the arc-chain outline" % what)
                            for t_ in tries:
                                log("       " + t_)
                            if c is not None:
                                log("       curve: " + describe(c))
                        return b
                tries.append("arc chain: no closed solid")
            except Exception as ex:
                tries.append("arc chain raised %s: %s" % (type(ex).__name__, ex))
        log("  !! %s: could not make a closed solid (outline added to _Debug)" % what)
        for t_ in tries:
            log("       " + t_)
        if c is not None:
            log("       curve: " + describe(c))
            DEBUG_CRV.append(c)
        return None

    def box(x0, x1, y0, y1, z0, z1):
        return rg.Box(rg.BoundingBox(min(x0, x1), min(y0, y1), min(z0, z1),
                                     max(x0, x1), max(y0, y1), max(z0, z1))).ToBrep()

    def cyl(x, y, z0, r, h):
        return rg.Cylinder(rg.Circle(rg.Plane(rg.Point3d(x, y, z0), rg.Vector3d.ZAxis), r), h).ToBrep(True, True)

    def fillet_edges(b, pred, radius, what):
        if b is None:
            return None
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

    # ---------- princess butterfly v5 ----------
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
        """vertical extrusion of a closed outline (dense point list -> periodic NURBS;
        arc-chain outline as fallback)"""
        try:
            crv = interp(pts2d, z0, closed=True)
        except Exception as ex:
            log("  .. %s: interpolation raised %s" % (what, ex))
            crv = None
        return extrude_curve(crv, z0, z1 - z0, what, fallback_segs=arc_chain(pts2d))

    def sharp_edges(min_deg=30.0):
        """edges whose two faces meet at more than min_deg (skips tangent seams)"""
        cmin = math.cos(math.radians(min_deg))

        def pred(e):
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

    def section_slab(fz, what):
        """a wing's smooth XZ section (top / bottom as functions of x) extruded along Y.
        Spline version first (side surface + planar caps); arc-chain version as fallback."""
        X0, X1, Y0, Y1 = -40.0, 40.0, -40.0, 40.0
        top, bot = section_pts(fz, X0, X1, 0.5)
        tries = []
        try:
            def spl(pts):
                l = List[rg.Point3d]()
                for (x, z) in pts:
                    l.Add(rg.Point3d(x, 0.0, z))
                return rg.Curve.CreateInterpolatedCurve(l, 3)
            P = lambda p: rg.Point3d(p[0], 0.0, p[1])
            cl = List[rg.Curve]()
            for c in (spl(top), rg.LineCurve(P(top[-1]), P(bot[-1])), spl(bot[::-1]), rg.LineCurve(P(bot[0]), P(top[0]))):
                cl.Add(c)
            j = rg.Curve.JoinCurves(cl, TOL)
            prof = j[0] if j is not None and len(j) == 1 and j[0].IsClosed else None
            if prof is None:
                tries.append("section did not join into one closed curve")
            else:
                prof.Translate(rg.Vector3d(0, Y0, 0))
                vec = rg.Vector3d(0, Y1 - Y0, 0)
                side = rg.Surface.CreateExtrusion(prof, vec).ToBrep()
                end = prof.DuplicateCurve()
                end.Translate(vec)
                pieces = [side]
                for k in (prof, end):
                    caps = rg.Brep.CreatePlanarBreps(k, TOL)
                    if caps is None or len(caps) == 0:
                        raise ValueError("CreatePlanarBreps returned nothing")
                    pieces.extend(caps)
                jb = rg.Brep.JoinBreps(blist(pieces), TOL)
                b = _closed_solid(jb[0]) if jb is not None and len(jb) == 1 else None
                if b is not None:
                    return b
                tries.append("spline slab not closed")
        except Exception as ex:
            tries.append("spline slab raised %s: %s" % (type(ex).__name__, ex))
        segs = arc_chain(top, closed=False)
        segs = chain(segs, [bot[-1]]) + arc_chain(bot[::-1], closed=False)
        segs = chain(segs, [top[0]])
        b = extrude_closed(segs, "XZ", rg.Vector3d(0, Y1 - Y0, 0), what + " (arc chain)")
        if b is not None:
            b.Translate(rg.Vector3d(0, Y0, 0))
            log("  .. %s: spline version failed (%s), used arcs" % (what, "; ".join(tries)))
        return b

    def bosses_and_holes(side):
        B = BF
        bh = B['BOSS_H'] + 0.2
        r_top = B['BOSS_D'] / 2
        r_bot = r_top - bh * math.tan(math.radians(B['BOSS_DRAFT']))
        adds = [revolve(pin_profile(r_bot, r_top, bh), "clip boss", (x, y, -B['BOSS_H'])) for (x, y) in boss_pos(side)]
        cuts = [revolve(hole_profile(B['CLIP_HOLE_D'] / 2, B['CLIP_HOLE_DEPTH']), "clip hole",
                        (x, y, -B['BOSS_H'])) for (x, y) in boss_pos(side)]
        return adds, cuts

    def wing(side):
        """side +1: P1 right wing (one smooth arc, thin end, round bar on the root edge)
        side -1: P2 left wing (thin organic plate, root edge curls into a small hook)"""
        B = BF
        adds, cuts = bosses_and_holes(side)
        if side > 0:
            log("Butterfly: P1 right wing (arc + bar)")
            slab = section_slab(right_z, "right wing section")
            outline = prism(right_outline_pts(), -5.0, 5.0, "right wing outline")
        else:
            log("Butterfly: P2 left wing (plate + hook)")
            slab = section_slab(left_z, "left wing section")
            outline = prism(left_outline_pts(), -5.0, 5.0, "left wing outline")
        if slab is None or outline is None:
            return None
        w = inter(slab, outline, "wing shape")
        w = fillet_edges(w, sharp_edges(), B['RIM_R'], "wing rim")
        if side > 0:
            xc, zc, y0, y1 = rod_axis()
            bar = rg.Brep.CreatePipe(rg.LineCurve(rg.Point3d(xc, y0, zc), rg.Point3d(xc, y1, zc)), B['ROD_R'],
                                     False, rg.PipeCapMode.Round, True, TOL, ATOL)
            if bar is None or len(bar) == 0:
                log("  !! bar pipe failed")
            else:
                adds = [solidify(bar[0], "bar")] + adds
        else:
            h0, h1 = hand_span()
            hook = extrude_closed(hand_profile(), "XZ", rg.Vector3d(0, h1 - h0 + 2.0, 0), "hook")
            if hook is not None:
                hook.Translate(rg.Vector3d(0, h0 - 1.0, 0))
                hook = inter(hook, prism(hand_plan(), -4.0, 0.6, "hook plan"), "hook rounded ends")
            adds = [hook] + adds
        part = union([w] + adds, "wing + %s + bosses" % ("bar" if side > 0 else "hook"))
        return diff(part, cuts, "clip holes")

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
            if parts[key] is None:
                out.append(None)
                continue
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

        import traceback

        def safe(fn, arg, name):
            try:
                r = fn(arg) if arg is not None else fn()
            except Exception:
                log("  !! %s raised an error:\n%s" % (name, traceback.format_exc()))
                return None
            if r is None:
                log("  !! %s: no solid produced" % name)
            return r
        parts = {'R': safe(wing, +1, "P1 right wing"), 'L': safe(wing, -1, "P2 left wing"),
                 'C': safe(clip_part, None, "P3 clip")}
        ax, ay, az = B['ASM_OFFSET']
        la = layer("Butterfly_Assembly", (245, 120, 180))
        add(parts['L'], la, "P2_wing_L (female)", (ax, ay, az))
        add(parts['R'], la, "P1_wing_R (male)", (ax, ay, az))
        if parts['C'] is not None:
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
            if b is None:
                continue
            add(b, lk, "packed_" + key)
            add(b, lk, "packed_" + key + "_section", (0, -E['STATE_DY'], 0))
        if DEBUG or DEBUG_CRV:
            ld = layer("_Debug", (255, 0, 0))
            for b in DEBUG:
                add(b, ld, "failed boolean operand")
            for c in DEBUG_CRV:
                a = Rhino.DocObjects.ObjectAttributes()
                a.LayerIndex = ld
                a.Name = "outline that would not extrude"
                c2 = c.DuplicateCurve()
                c2.Transform(SCALE)
                doc.Objects.AddCurve(c2, a)
        doc.Views.Redraw()
        fails = [m for m in LOG if m.strip().startswith("!!")]
        made = ", ".join(k for k in ('R', 'L', 'C') if parts.get(k) is not None)
        summary = "kinder_rhino_build: parts built = %s; %d warnings" % (made, len(fails))
        print("---- done: " + summary)
        import os
        path = None
        for d in (os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else None,
                  os.path.expanduser("~")):
            if d:
                try:
                    path = os.path.join(d, "kinder_build_log.txt")
                    with open(path, "w") as f:
                        f.write(summary + "\n" + "\n".join(LOG) + "\n")
                    break
                except Exception:
                    path = None
        if fails:
            try:
                Rhino.UI.Dialogs.ShowMessage(summary + "\n\n" + "\n".join(LOG[-40:]) +
                                             ("\n\nFull log: %s" % path if path else ""), "Kinder toy build log")
            except Exception:
                pass

    if __name__ == "__main__":
        main()
