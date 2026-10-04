# -*- coding: utf-8 -*-
"""
Kinder Surprise capsule + "Fairytale Princess" butterfly hair clip, built from scratch with RhinoCommon.

How to run (Rhino 7 / 8 / 9 WIP, Windows or Mac):
    Rhino command line  ->  RunPythonScript  ->  pick this file
    or ScriptEditor -> open this file -> Run (IronPython 2 or CPython 3 both work)

Everything is parametric: edit EGG / BF below and run again.
Objects created by a previous run (layer tree "KinderToy") are deleted first.

Toy (4 parts, injection moulded ABS, no metal, all straight-pull tools):
    P1 right wing  - lies on top; jewel medallion + 2 S-hooks underneath
    P2 left wing   - lies below; heart medallion + 2 arc slots the hooks snap through
    P3 clip x2     - identical one-piece ABS spring clip, press-fits under either wing

Output layers (parent "KinderToy"):
    Egg_Closed / Egg_HalfOpen / Egg_Open      capsule with wall thickness, 3 hinge states
    Egg_Closed_Section                        closed capsule cut in half + packed toy inside
    Butterfly_Assembly                        4 parts assembled
    Butterfly_Parts                           P1, P2, P3 laid out
    Packed_In_Egg                             4 parts in their packing position (inside Egg_Closed)
    _Debug                                    only filled if a boolean failed (see command line)

Units: all parameters are millimetres. If the document is in another unit the result is scaled.
The geometry maths (profiles, outlines, hooks, packing) is plain Python and is cross-checked
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
# PARAMETERS - "FAIRYTALE PRINCESS" BUTTERFLY HAIR CLIP  (4 parts, ABS, no metal)
# assembled frame: X = span (right wing +X), Y = head direction, Z = up.
# Each wing is modelled in its own local Z (plate z 0..T); in the assembly the right wing
# lies on top of the left wing (right wing z offset = T).
# =====================================================================================
BF = dict(
    T=1.6,                       # wing plate thickness
    # right-wing outline = uniform periodic cubic B-spline through these control points
    CTRL=[(1.2, 3.0), (1.6, 9.0), (4.2, 15.5), (9.0, 20.6), (15.5, 22.0), (20.0, 19.6),
          (21.2, 14.2), (18.6, 8.6), (14.6, 5.0), (11.4, 2.0), (14.4, -0.6), (17.6, -4.6),
          (18.0, -9.8), (14.8, -13.8), (9.6, -14.6), (5.2, -11.6), (2.4, -6.6), (1.2, -2.5)],
    SAMPLES=24,                  # samples per span (verification / border offset)
    EDGE_FILLET=0.5,             # top edge fillet of plate and medallion
    # root medallion (round "OO" overlap): right wing centre (-MED_X, 0), left (+MED_X, 0)
    MED_R=5.0, MED_X=1.5,
    # raised decoration on the top face (UV colour-change coating goes over it)
    BORDER_OFF=1.4, BORDER_R=0.40, BORDER_XMIN=7.0,   # inner border bead, starts away from the root
    DECO_Z=-0.08,                # pipe centre below top face -> raised ~0.3
    VEIN_R=0.42,
    VEINS=[[(7.6, 5.0), (9.6, 9.6), (12.4, 14.0), (15.6, 16.8), (18.0, 16.6), (18.2, 14.6), (16.9, 14.0)],
           [(8.4, 3.6), (11.8, 6.2), (15.4, 8.4), (17.8, 11.0), (17.0, 12.4)],
           [(7.6, -2.6), (9.4, -6.2), (11.6, -9.6), (13.8, -11.4), (15.2, -10.0), (14.2, -8.9)],
           [(8.6, -1.4), (11.8, -2.8), (14.6, -4.6), (15.6, -6.6)]],
    PEARLS=[(11.6, 11.6, 0.55), (15.2, 13.2, 0.48), (13.6, 9.4, 0.38),
            (10.8, -6.6, 0.48), (13.4, -7.4, 0.40), (6.6, 9.2, 0.38)],
    # right wing: cabochon gem + bezel + bead ring on the medallion (the butterfly "body" jewel)
    GEM_R=3.0, GEM_H=1.3, BEZEL_R=3.35, BEZEL_PIPE=0.35, BEAD_RING=4.35, BEAD_N=14, BEAD_R=0.36,
    # left wing: recessed heart on its medallion (hidden under the jewel when assembled)
    HEART_W=5.2, HEART_D=0.35,
    # S-hook snap: 2 hooks under the right medallion edge, through 2 arc slots in the left wing
    HOOK_ANG=[130.0, 230.0],     # hook centre angles around the right medallion centre (deg)
    HOOK_SPAN=3.0,               # hook length along the arc (mm, at MED_R)
    HOOK_T=0.6,                  # hook web thickness (radial)
    LIP=0.25,                    # lip overhang = catch engagement
    LIP_CLR=0.05,                # gap between lip and the left wing underside
    LEAD_H=0.85,                 # 45 deg lead-in height below the lip
    RELIEF_W=0.5, RELIEF_D=1.0,  # relief groove inside the hook (from below): longer, softer hook
    KEY_SPAN=1.2, KEY_GAP=0.6,   # rigid key next to each hook: stops the wing sliding inward
    SLOT_IN=0.85, SLOT_OUT=0.05, SLOT_CLR=0.15,   # slot radial extents / end clearance
    # clip interface (same clip as before)
    BOSS_D=5.0, BOSS_H=1.5, BOSS_DRAFT=1.0,
    CLIP_PIN_D=2.25, CLIP_HOLE_D=2.20, CLIP_PIN_H=2.1, CLIP_HOLE_DEPTH=2.3,
    BOSS_POS=[(10.5, -6.8), (10.5, 9.2)],       # right wing; mirrored for the left
    CLIP_W=7.0, CLIP_L=24.0, CLIP_T=1.4, CLIP_PIN_Y=[4.0, 20.0],
    ASM_OFFSET=(110.0, 0.0, 0.0),
    PARTS_OFFSET=(170.0, 0.0, 0.0),
)

# packing in the closed capsule: part, (rot about X deg, rot about Z deg, dx, dy, dz) applied to the
# part's local frame; found and verified (no clash with the real shell) by ../verify_rhino_math.py
PACK = [("R", (90, 0, -7.066, -2.065, 19.024)),
        ("L", (-90, 0, 7.066, 2.935, 26.296)),
        ("C", (90, 0, -3.500, 7.465, 10.810)),
        ("C", (90, 180, 3.500, -7.465, 10.810))]

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


# ---------------- princess butterfly maths ----------------
def bspline_closed(ctrl, n):
    """uniform periodic cubic B-spline (same curve as Rhino NurbsCurve.Create(True, 3, ctrl))"""
    m = len(ctrl)
    out = []
    for i in range(m):
        p0, p1, p2, p3 = ctrl[i - 1], ctrl[i], ctrl[(i + 1) % m], ctrl[(i + 2) % m]
        for k in range(n):
            t = k / n
            b0 = (1 - t) ** 3 / 6
            b1 = (3 * t ** 3 - 6 * t ** 2 + 4) / 6
            b2 = (-3 * t ** 3 + 3 * t ** 2 + 3 * t + 1) / 6
            b3 = t ** 3 / 6
            out.append((b0 * p0[0] + b1 * p1[0] + b2 * p2[0] + b3 * p3[0],
                        b0 * p0[1] + b1 * p1[1] + b2 * p2[1] + b3 * p3[1]))
    return out


def mirror_pts(pts, side):
    return [(side * p[0], p[1]) for p in pts]


def wing_ctrl(side, B=BF):
    c = mirror_pts(B['CTRL'], side)
    return c if side > 0 else c[::-1]


def wing_outline_pts(side, B=BF):
    return bspline_closed(wing_ctrl(side, B), B['SAMPLES'])


def _area(pts):
    return 0.5 * sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))


def offset_closed(pts, d):
    """offset a closed polyline inward by d (d > 0)"""
    ccw = _area(pts) > 0
    out = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i - 1], pts[(i + 1) % n]
        tx, ty = _unit((b[0] - a[0], b[1] - a[1]))
        nx, ny = (-ty, tx) if ccw else (ty, -tx)        # inward normal
        out.append((pts[i][0] + nx * d, pts[i][1] + ny * d))
    return out


def border_pts(side, B=BF):
    """inner border bead path(s): offset outline, only where |x| > BORDER_XMIN (clear of the overlap)"""
    off = offset_closed(wing_outline_pts(side, B), B['BORDER_OFF'])
    keep = [side * p[0] > B['BORDER_XMIN'] for p in off]
    n = len(off)
    start = next(i for i in range(n) if not keep[i])
    runs, cur = [], []
    for k in range(1, n + 1):
        i = (start + k) % n
        if keep[i]:
            cur.append(off[i])
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return [r[::3] + ([r[-1]] if (len(r) - 1) % 3 else []) for r in runs if len(r) > 6]


def vein_pts(side, B=BF):
    return [mirror_pts(v, side) for v in B['VEINS']]


def pearl_pts(side, B=BF):
    return [(side * x, y, r) for (x, y, r) in B['PEARLS']]


def boss_pos(side, B=BF):
    return mirror_pts(B['BOSS_POS'], side)


def medallion_c(side, B=BF):
    """right wing medallion sits at -MED_X (over the left wing), left wing medallion at +MED_X"""
    return (-side * B['MED_X'], 0.0)


def heart_pts(B=BF, n=48):
    """closed heart outline on the left medallion"""
    cx, cy = medallion_c(-1, B)
    s = B['HEART_W'] / 32.0
    pts = []
    for i in range(n):
        t = 2 * math.pi * (i + 0.5) / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * s, cy + (y + 2.5) * s))
    return pts


def _deg(mm, B=BF):
    return math.degrees(mm / B['MED_R'])


def hook_spans(B=BF):
    """(a0, a1) angle ranges of the hooks, and of the keys, around the right medallion centre"""
    hs, kg, ks = _deg(B['HOOK_SPAN']) / 2, _deg(B['KEY_GAP']), _deg(B['KEY_SPAN'])
    hooks, keys = [], []
    for a in B['HOOK_ANG']:
        hooks.append((a - hs, a + hs))
        if a < 180:   # key on the side towards 180 deg
            keys.append((a + hs + kg, a + hs + kg + ks))
        else:
            keys.append((a - hs - kg - ks, a - hs - kg))
    return hooks, keys


def slot_spans(B=BF):
    hooks, keys = hook_spans(B)
    c = _deg(B['SLOT_CLR'])
    return [(min(h[0], k[0]) - c, max(h[1], k[1]) + c) for h, k in zip(hooks, keys)]


def hook_profile(B=BF):
    """closed (r, z) section of a hook, right-wing local z (underside z = 0, plate 0..T)."""
    R, t = B['MED_R'], B['T']
    zc = -(t + B['LIP_CLR'])                     # catch level (under the left wing)
    rin = R - B['HOOK_T']
    top = B['RELIEF_D'] + EPS                     # web root inside the plate (above the relief)
    # web is 0.1 inside the medallion edge where it merges with the plate (no coincident
    # cylinder faces in the boolean), then steps out flush with the edge below the underside
    pts = [(rin, top), (R - 0.1, top), (R - 0.1, 0.05), (R, -0.05), (R, zc), (R + B['LIP'], zc - B['LIP']),
           (R + B['LIP'], zc - B['LIP'] - 0.1), (rin, zc - B['LIP'] - 0.1 - B['LEAD_H'] - B['LIP'])]
    return [('L', pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def rect_profile(r0, r1, z0, z1):
    pts = [(r0, z0), (r1, z0), (r1, z1), (r0, z1)]
    return [('L', pts[i], pts[(i + 1) % 4]) for i in range(4)]


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


def check_princess(B=BF):
    """layout sanity checks (pure python). Returns dict name -> (ok, detail)."""
    res = {}
    R, L = wing_outline_pts(+1, B), wing_outline_pts(-1, B)
    mc = medallion_c(+1, B)

    def inner(poly, p, m):
        return point_in_poly(p, poly) and dist_to_poly(p, poly) >= m

    def arc(c, r, a0, a1, n=12):
        return [(c[0] + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                 c[1] + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
    # bosses well inside both wings
    m = min(dist_to_poly(p, R) for p in boss_pos(+1, B))
    res['boss margin'] = (m >= B['BOSS_D'] / 2 + 1.0, round(m, 2))
    # slots fully inside the left wing with >= 0.8 mm material around
    pts = []
    for (a0, a1) in slot_spans(B):
        for r in (B['MED_R'] - B['SLOT_IN'], B['MED_R'] + B['SLOT_OUT']):
            pts += arc(mc, r, a0, a1)
    m = min(dist_to_poly(p, L) if point_in_poly(p, L) else -1 for p in pts)
    res['slot inside left wing'] = (m >= 0.8, round(m, 2))
    # hook lips must have nothing of the right wing above them (straight pull)
    hooks, keys = hook_spans(B)
    lip = []
    for (a0, a1) in hooks:
        lip += arc(mc, B['MED_R'] + B['LIP'] + 0.3, a0, a1)
    bad = [p for p in lip if point_in_poly(p, R)]
    res['lips clear of right wing'] = (not bad, len(bad))
    # raised decoration of the left wing must be outside the right wing footprint (+0.5)
    def in_right_fp(p, mg):
        return (point_in_poly(p, R) or dist_to_poly(p, R) < mg or
                math.hypot(p[0] - mc[0], p[1] - mc[1]) < B['MED_R'] + mg)
    deco = [q for v in vein_pts(-1, B) for q in v] + [(x, y) for (x, y, r) in pearl_pts(-1, B)]
    deco += [q for b in border_pts(-1, B) for q in b]
    bad = [p for p in deco if in_right_fp(p, 0.6)]
    res['left deco clear of right wing'] = (not bad, len(bad))
    # decoration inside the outline
    deco_r = [q for v in vein_pts(+1, B) for q in v] + [(x, y) for (x, y, r) in pearl_pts(+1, B)]
    m = min(dist_to_poly(p, R) if point_in_poly(p, R) else -1 for p in deco_r)
    res['deco inside outline'] = (m >= 1.2, round(m, 2))
    # wing size (packing)
    xs, ys = [p[0] for p in R], [p[1] for p in R]
    res['wing size'] = (True, (round(max(xs) - min(min(xs), mc[0] - B['MED_R']), 2), round(max(ys) - min(ys), 2)))
    # hook snap strain  (cantilever: eps = 1.5 t d / L^2)
    Lh = B['RELIEF_D'] + B['T'] + B['LIP_CLR'] + B['LIP']
    eps = 1.5 * B['HOOK_T'] * (B['LIP'] - B['SLOT_OUT']) / Lh ** 2
    res['hook strain'] = (eps <= 0.025, "%.1f %%" % (eps * 100))
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

    # ---------- princess butterfly ----------
    def pts3(pts2d, z):
        l = List[rg.Point3d]()
        for (x, y) in pts2d:
            l.Add(rg.Point3d(x, y, z))
        return l

    def interp(pts2d, z, closed=False):
        if closed:
            return rg.Curve.CreateInterpolatedCurve(pts3(pts2d, z), 3, rg.CurveKnotStyle.ChordPeriodic)
        return rg.Curve.CreateInterpolatedCurve(pts3(pts2d, z), 3)

    def pipe(crv, r, what):
        res = rg.Brep.CreatePipe(crv, r, False, rg.PipeCapMode.Round, True, TOL, ATOL)
        if res is None or len(res) == 0:
            log("  !! pipe %s failed" % what)
            return None
        return solidify(res[0], what)

    def revolve_about(segs, center, a0, a1, what):
        """revolve a closed (r, z) profile around the vertical axis through center, from a0 to a1 deg"""
        cx, cy = center
        axis = rg.Line(rg.Point3d(cx, cy, -100), rg.Point3d(cx, cy, 100))
        faces = []
        for c in seg_curves(segs, "XZ"):
            c.Translate(rg.Vector3d(cx, cy, 0))
            rs = rg.RevSurface.Create(c, axis, math.radians(a0), math.radians(a1))
            faces.append(rg.Brep.CreateFromRevSurface(rs, False, False))
        j = rg.Brep.JoinBreps(blist(faces), TOL)
        if j is None or len(j) == 0:
            log("  !! revolve %s failed" % what)
            return None
        b = j[0]
        if not b.IsSolid:
            b = b.CapPlanarHoles(TOL)
        return solidify(b, what)

    def disc(c, r, z0, h, fillet, what):
        d = cyl(c[0], c[1], z0, r, h)
        return fillet_edges(d, edge_at_z(z0 + h), fillet, what) if fillet > 0 else d

    def wing(side):
        """side +1: right wing (top, jewel + 2 S-hooks), -1: left wing (bottom, heart + 2 slots).
        Local frame: plate z 0..T, underside z = 0."""
        B = BF
        t = B['T']
        mc = medallion_c(side)
        log("Butterfly: %s wing" % ("right" if side > 0 else "left"))
        outline = rg.NurbsCurve.Create(True, 3, pts3(wing_ctrl(side), 0.0))
        plate = extrude_curve(outline, 0.0, t, "wing plate")
        plate = fillet_edges(plate, edge_at_z(t), B['EDGE_FILLET'], "wing plate top edge")
        adds = [plate, disc(mc, B['MED_R'], 0.0, t, B['EDGE_FILLET'], "medallion top edge")]
        zd = t + B['DECO_Z']
        for pts in border_pts(side):
            adds.append(pipe(interp(pts, zd), B['BORDER_R'], "border bead"))
        for v in vein_pts(side):
            adds.append(pipe(interp(v, zd), B['VEIN_R'], "vein"))
        for (x, y, r) in pearl_pts(side):
            adds.append(rg.Sphere(rg.Point3d(x, y, t - 0.12), r).ToBrep())
        bh = B['BOSS_H'] + 0.2
        r_top = B['BOSS_D'] / 2
        r_bot = r_top - bh * math.tan(math.radians(B['BOSS_DRAFT']))
        for (x, y) in boss_pos(side):
            adds.append(revolve(pin_profile(r_bot, r_top, bh), "clip boss", (x, y, -B['BOSS_H'])))
        cuts = [revolve(hole_profile(B['CLIP_HOLE_D'] / 2, B['CLIP_HOLE_DEPTH']), "clip hole",
                        (x, y, -B['BOSS_H'])) for (x, y) in boss_pos(side)]
        if side > 0:
            # jewel: cabochon (sphere cap) + bezel + bead ring
            rs = (B['GEM_R'] ** 2 + B['GEM_H'] ** 2) / (2 * B['GEM_H'])
            sph = rg.Sphere(rg.Point3d(mc[0], mc[1], t + B['GEM_H'] - rs), rs).ToBrep()
            gem = inter(sph, box(mc[0] - 10, mc[0] + 10, -10, 10, t - EPS, t + 5), "gem cap")
            adds.append(gem)
            ring = rg.Circle(rg.Plane(rg.Point3d(mc[0], mc[1], zd), rg.Vector3d.ZAxis), B['BEZEL_R'])
            adds.append(pipe(rg.ArcCurve(ring), B['BEZEL_PIPE'], "bezel"))
            for i in range(B['BEAD_N']):
                a = 2 * math.pi * (i + 0.5) / B['BEAD_N']
                adds.append(rg.Sphere(rg.Point3d(mc[0] + B['BEAD_RING'] * math.cos(a),
                                                 mc[1] + B['BEAD_RING'] * math.sin(a), t - 0.05),
                                      B['BEAD_R']).ToBrep())
            # S-hooks + keys (under the medallion edge), relief grooves inside the hooks
            hooks, keys = hook_spans()
            R = B['MED_R']
            for (a0, a1) in hooks:
                adds.append(revolve_about(hook_profile(), mc, a0, a1, "S-hook"))
                cuts.append(revolve_about(rect_profile(R - B['HOOK_T'] - B['RELIEF_W'], R - B['HOOK_T'],
                                                       -0.5, B['RELIEF_D']), mc, a0 - 1.0, a1 + 1.0, "relief"))
            for (a0, a1) in keys:
                adds.append(revolve_about(rect_profile(R - B['SLOT_IN'] + 0.03, R - B['SLOT_IN'] + 0.63,
                                                       -t, 0.3), mc, a0, a1, "key"))
        else:
            # recessed heart on the medallion + the 2 arc slots for the hooks
            heart = interp(heart_pts(), t - B['HEART_D'], closed=True)
            cuts.append(extrude_curve(heart, t - B['HEART_D'], B['HEART_D'] + 1.0, "heart"))
            R = B['MED_R']
            for (a0, a1) in slot_spans():
                cuts.append(revolve_about(rect_profile(R - B['SLOT_IN'], R + B['SLOT_OUT'], -1.0, t + 1.0),
                                          medallion_c(+1), a0, a1, "hook slot"))
        part = union(adds, "wing + decoration")
        return diff(part, [c for c in cuts if c is not None], "wing cuts")

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
        """packing inside the closed capsule (positions verified in verify_rhino_math.py)"""
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
        T = B['T']
        ax, ay, az = B['ASM_OFFSET']
        la = layer("Butterfly_Assembly", (245, 120, 180))
        add(parts['L'], la, "wing_L (bottom)", (ax, ay, az))
        add(parts['R'], la, "wing_R (top)", (ax, ay, az + T))
        add(clip_on_wing(parts['C'], -1), la, "clip_L", (ax, ay, az))
        add(clip_on_wing(parts['C'], +1), la, "clip_R", (ax, ay, az + T))
        lp = layer("Butterfly_Parts", (120, 160, 245))
        ox, oy, oz = B['PARTS_OFFSET']
        add(parts['R'], lp, "P1_wing_R", (ox, oy, oz), dict(material="ABS + UV colour-change coating"))
        add(parts['L'], lp, "P2_wing_L", (ox + 50, oy, oz), dict(material="ABS + UV colour-change coating"))
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
