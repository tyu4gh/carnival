# -*- coding: utf-8 -*-
"""
"Fairytale Princess" butterfly hair-clip toy for the Kinder Surprise capsule - RhinoCommon build.

4 ABS parts, no metal:
    P1  Wing R  (lower half of the centre overlap + up-lip arc)
    P2  Wing L  (upper half of the centre overlap + down-lip arc)
    P3  Clip x2 (identical one-piece spring clip, pressed under either wing)
The two wings overlap at the centre and lock into each other with two arc-shaped lips
(sketch "WING CONNECT"): each lip drops into a matching arc slot of the other wing.
Pressed together vertically -> one butterfly; pulled apart -> two hair clips.

How to run (Rhino 7 / 8 / 9 WIP):
    command line  ->  RunPythonScript  ->  pick this file
    (or ScriptEditor, IronPython 2.7 or CPython 3)
All parameters are at the top (PR = butterfly, EGG = capsule). Edit and run again;
objects of the previous run (layer tree "KinderPrincess") are replaced.

Layers (parent "KinderPrincess"):
    Butterfly_Assembly   assembled butterfly with 2 clips
    Butterfly_Exploded   the same, exploded vertically (assembly direction)
    Parts                P1, P2, P3 laid flat (mould orientation)
    Egg_Closed / Egg_Open / Egg_Closed_Section   capsule, and section with the packed toy
    Packed_In_Egg        the 4 parts in packing position
    _Debug               only used if a boolean failed (see command line for "!!")
Units: millimetres (scaled automatically if the document uses another unit).
The geometry maths is plain Python so it can be verified outside Rhino (../verify.py).
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
# PARAMETERS - PRINCESS BUTTERFLY
# assembled frame: X = span (right wing +X), Y = up the hair (top lobes +Y), Z = up (decor side)
# =====================================================================================
BF = dict(
    T=2.0,                    # wing thickness
    SPLIT=1.0,                # height of the overlap interface (R below, L above)
    # right wing outline (closed periodic spline): big rounded upper lobe, smaller lower lobe
    WING_PTS=[(0.5, 3.0), (3.0, 8.0), (7.0, 14.0), (12.0, 17.5), (17.0, 18.0), (21.0, 15.5),
              (22.5, 11.0), (21.0, 6.5), (17.0, 3.0), (13.5, 1.0), (16.0, -2.0), (18.5, -6.5),
              (18.0, -11.0), (14.5, -14.0), (10.0, -14.0), (6.0, -10.5), (3.0, -5.5), (0.5, -2.5)],
    HUB_C=(-1.0, 0.0),        # centre of the right wing's overlap disc (reaches under the left wing)
    HUB_R=4.8,
    ROOT_FILLET=1.0,          # 2D fillet where hub disc meets the wing outline
    # interlocking arc lips (concentric with the hub disc, inset from its edge)
    LIP_IN=1.6, LIP_OUT=0.7,  # lip band = hub radius - LIP_IN .. hub radius - LIP_OUT
    LIP_ANG=55.0,             # half angle of the lip arc (deg)
    LIP_FIT=0.02,             # slot narrower than lip on each side (press fit)
    # UV-colour-change relief on the top face (raised, rounded, no sharp edges)
    FRAME_UP=[(8.5, 10.5), (12.0, 14.8), (17.0, 15.7), (20.0, 13.5), (20.5, 10.0), (18.5, 6.5),
              (14.5, 4.5), (10.5, 6.0)],
    FRAME_LO=[(9.0, -6.5), (13.0, -3.8), (16.0, -5.5), (16.6, -9.5), (14.0, -12.2), (10.5, -11.8),
              (8.5, -9.5)],
    FRAME_R=0.35,             # half-round bead radius (relief height 0.35)
    VEINS=[[(11.0, 7.5), (14.5, 10.5), (17.5, 12.3)],
           [(10.5, 8.8), (12.5, 11.8), (14.0, 13.3)],
           [(10.8, -8.0), (12.8, -8.8), (14.3, -10.0)]],
    VEIN_R=0.28,
    PEARLS=[(7.8, 12.8), (9.8, 15.0), (7.4, -9.0), (12.6, 2.4), (12.4, -2.3)],
    PEARL_R=0.6, PEARL_Z=-0.15,   # pearl centre relative to the top face
    # clip mounting bosses under the wing
    BOSS_D=5.0, BOSS_H=1.2, BOSS_DRAFT=1.0,
    BOSS_POS=[(11.0, -6.0), (11.0, 10.0)],
    CLIP_PIN_D=2.25, CLIP_HOLE_D=2.20, CLIP_PIN_H=2.1, CLIP_HOLE_DEPTH=2.3,
    CLIP_W=7.0, CLIP_L=24.0, CLIP_T=1.4, CLIP_PIN_Y=[4.0, 20.0],
    # layout in the document
    ASM_OFFSET=(110.0, 0.0, 0.0), EXPL_OFFSET=(170.0, 0.0, 0.0), PARTS_OFFSET=(230.0, 0.0, 0.0),
)

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




# ---------- princess butterfly maths ----------
def mirror_pts(pts):
    return [(-x, y) for (x, y) in pts]


def circle_segs(c, r):
    cx, cy = c
    return [('A', (cx + r, cy), (cx, cy + r), (cx - r, cy)), ('A', (cx - r, cy), (cx, cy - r), (cx + r, cy))]


def annular_sector(c, r0, r1, a_mid, half):
    """closed outline of a ring sector (degrees)"""
    cx, cy = c

    def P(r, a):
        return (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
    a0, a1 = a_mid - half, a_mid + half
    return [('A', P(r1, a0), P(r1, a_mid), P(r1, a1)), ('L', P(r1, a1), P(r0, a1)),
            ('A', P(r0, a1), P(r0, a_mid), P(r0, a0)), ('L', P(r0, a0), P(r1, a0))]


def hubs(B=BF):
    """(centre, r) of right and left hub discs"""
    cR = B['HUB_C']
    return (cR, B['HUB_R']), ((-cR[0], cR[1]), B['HUB_R'])


def lip_band(side, fit=0.0, B=BF):
    """lip arc of wing `side` (+1 right / -1 left); fit > 0 gives the (narrower) slot in the other wing.
    Right wing lip sits at the far (-X) edge of its hub, left wing lip at the far (+X) edge of its hub."""
    (cR, r), (cL, _) = hubs(B)
    c, a_mid = (cR, 180.0) if side > 0 else (cL, 0.0)
    return annular_sector(c, r - B['LIP_IN'] + fit, r - B['LIP_OUT'] - fit, a_mid, B['LIP_ANG'])


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
        joined = rg.Curve.JoinCurves(crvs, TOL)
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

    # ---------- butterfly ----------
    def outline_curve(pts, z=0.0, periodic=True):
        l = List[rg.Point3d]()
        for (x, y) in pts:
            l.Add(rg.Point3d(x, y, z))
        if periodic:
            return rg.Curve.CreateInterpolatedCurve(l, 3, rg.CurveKnotStyle.ChordPeriodic)
        return rg.Curve.CreateInterpolatedCurve(l, 3)

    def footprint(side):
        """wing outline united with its hub disc, inner corners filleted (2D)"""
        B = BF
        pts = B['WING_PTS'] if side > 0 else mirror_pts(B['WING_PTS'])
        (cR, r), (cL, _) = hubs()
        c = cR if side > 0 else cL
        crvs = List[rg.Curve]()
        crvs.Add(outline_curve(pts))
        crvs.Add(rg.ArcCurve(rg.Circle(rg.Point3d(c[0], c[1], 0), r)))
        u = rg.Curve.CreateBooleanUnion(crvs, TOL)
        if u is None or len(u) != 1:
            log("  !! footprint union (%s) gave %s curves - using outline only" % (side, None if u is None else len(u)))
            return crvs[0]
        f = u[0]
        try:
            ff = rg.Curve.CreateFilletCornersCurve(f, B['ROOT_FILLET'], TOL, ATOL)
            if ff is not None and ff.IsClosed:
                f = ff
        except Exception as ex:
            log("  .. root fillet skipped (%s)" % ex)
        return f

    def slab(segs, z0, z1, what):
        b = extrude_closed(segs, "XY", rg.Vector3d(0, 0, z1 - z0), what)
        b.Transform(rg.Transform.Translation(0, 0, z0))
        return b

    def decor(side):
        """UV-colour relief on the top face: lobe frames, veins, pearls"""
        B = BF
        T = B['T']
        m = (lambda p: p) if side > 0 else mirror_pts
        out = []
        for pts in (B['FRAME_UP'], B['FRAME_LO']):
            p = rg.Brep.CreatePipe(outline_curve(m(pts), T), B['FRAME_R'], False, getattr(rg.PipeCapMode, "None"),
                                   True, TOL, ATOL)
            if p is not None and len(p):
                out.append(solidify(p[0], "frame bead"))
            else:
                log("  !! frame pipe failed")
        for pts in B['VEINS']:
            p = rg.Brep.CreatePipe(outline_curve(m(pts), T, False), B['VEIN_R'], False, rg.PipeCapMode.Round,
                                   True, TOL, ATOL)
            if p is not None and len(p):
                out.append(solidify(p[0], "vein"))
            else:
                log("  !! vein pipe failed")
        for (x, y) in m(B['PEARLS']):
            out.append(rg.Sphere(rg.Point3d(x, y, T + B['PEARL_Z']), B['PEARL_R']).ToBrep())
        return out

    def wing(side, F_self, F_other):
        B = BF
        T, S = B['T'], B['SPLIT']
        name = "P1 wing R" if side > 0 else "P2 wing L"
        log("Butterfly: " + name)
        w = extrude_curve(F_self, 0.0, T, name + " footprint")
        if side > 0:   # right wing keeps the LOWER half of the overlap, its lip rises into the left wing
            w = diff(w, [extrude_curve(F_other, S, T + 1.0, "overlap cutter")], "overlap top half")
            w = union([w, slab(lip_band(+1), S - 0.1, T, "up-lip")], "up-lip")
            slot = slab(lip_band(-1, B['LIP_FIT']), -1.0, T + 1.0, "slot")
        else:          # left wing keeps the UPPER half, its lip drops into the right wing
            w = diff(w, [extrude_curve(F_other, -1.0, S + 1.0, "overlap cutter")], "overlap bottom half")
            w = union([w, slab(lip_band(-1), 0.0, S + 0.1, "down-lip")], "down-lip")
            slot = slab(lip_band(+1, B['LIP_FIT']), -1.0, T + 1.0, "slot")
        w = diff(w, [slot], "lip slot")
        w = union([w] + decor(side), "UV relief")
        bh = B['BOSS_H'] + 0.2
        r_top = B['BOSS_D'] / 2
        r_bot = r_top - bh * math.tan(math.radians(B['BOSS_DRAFT']))
        pos = [(x * side, y) for (x, y) in B['BOSS_POS']]
        w = union([w] + [revolve(pin_profile(r_bot, r_top, bh), "boss", (x, y, -B['BOSS_H'])) for (x, y) in pos],
                  "clip bosses")
        w = diff(w, [revolve(hole_profile(B['CLIP_HOLE_D'] / 2, B['CLIP_HOLE_DEPTH']), "clip hole",
                             (x, y, -B['BOSS_H'])) for (x, y) in pos], "clip holes")
        return w

    def clip_part():
        B = BF
        log("Butterfly: P3 clip")
        c = extrude_closed(clip_outline(), "YZ", rg.Vector3d(B['CLIP_W'], 0, 0), "clip profile")
        pins = [revolve(pin_profile(B['CLIP_PIN_D'] / 2, B['CLIP_PIN_D'] / 2, B['CLIP_PIN_H'] + 0.1, 0.35),
                        "clip pin", (B['CLIP_W'] / 2, y, -0.1)) for y in B['CLIP_PIN_Y']]
        return union([c] + pins, "clip pins")

    def clip_on_wing(c, side):
        B = BF
        x, y = B['BOSS_POS'][0]
        t = rg.Transform.Translation(x - B['CLIP_W'] / 2, y - B['CLIP_PIN_Y'][0], -B['BOSS_H'])
        p = xf(c, t)
        return xf(p, MIRROR_X) if side < 0 else p

    def pack_in_egg(parts):
        """wings back to back in the middle, clips on both sides; all along the egg axis"""
        E = EGG
        zc = (E['T'] + E['L_TOTAL'] - E['T']) / 2
        r90 = rg.Transform.Rotation(math.pi / 2, rg.Vector3d.XAxis, rg.Point3d.Origin)

        def centred(b, rot_z180=False):
            c = xf(b, r90)
            if rot_z180:
                c = xf(c, rg.Transform.Rotation(math.pi, rg.Vector3d.ZAxis, rg.Point3d.Origin))
            bb = c.GetBoundingBox(True)
            m = bb.Center
            c.Transform(rg.Transform.Translation(-m.X, -m.Y, -m.Z))
            return c, bb.Max.Y - bb.Min.Y
        gap = 0.3
        wr, tr = centred(parts['P1'])
        wl, tl = centred(parts['P2'])
        c1, tc = centred(parts['P3'])
        c2, _ = centred(parts['P3'], True)
        out = []
        for b, dy in ((wr, -(tr / 2 + gap / 2)), (wl, tl / 2 + gap / 2),
                      (c1, tl + gap + tc / 2 + gap), (c2, -(tr + gap + tc / 2 + gap))):
            out.append(xf(b, rg.Transform.Translation(0, dy, zc)))
        return out

    # ---------- document ----------
    ROOT = "KinderPrincess"

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
        a.SetUserString("generator", "princess_butterfly_rhino.py")
        for k, v in (info or {}).items():
            a.SetUserString(k, str(v))
        doc.Objects.AddBrep(c, a)

    def main():
        if doc.ModelUnitSystem != Rhino.UnitSystem.Millimeters:
            log("Document units are %s - geometry is scaled from mm." % doc.ModelUnitSystem)
        clear_previous()
        E, B = EGG, BF

        F_R, F_L = footprint(+1), footprint(-1)
        parts = {'P1': wing(+1, F_R, F_L), 'P2': wing(-1, F_L, F_R), 'P3': clip_part()}
        info = dict(material="ABS + photochromic (UV) colour", theme="fairytale princess")

        la = layer("Butterfly_Assembly", (245, 150, 200))
        asm = [("P1_wing_R", parts['P1']), ("P2_wing_L", parts['P2']),
               ("P3_clip_R", clip_on_wing(parts['P3'], +1)), ("P3_clip_L", clip_on_wing(parts['P3'], -1))]
        for nm, b in asm:
            add(b, la, nm, B['ASM_OFFSET'], info)
        le = layer("Butterfly_Exploded", (200, 170, 245))
        ex = B['EXPL_OFFSET']
        for (nm, b), dz in zip(asm, (0.0, 8.0, -8.0, -8.0)):
            add(b, le, nm, (ex[0], ex[1], ex[2] + dz))
        lp = layer("Parts", (120, 160, 245))
        ox, oy, oz = B['PARTS_OFFSET']
        add(parts['P1'], lp, "P1_wing_R", (ox, oy, oz), info)
        add(parts['P2'], lp, "P2_wing_L", (ox + 50, oy, oz), info)
        add(parts['P3'], lp, "P3_clip (x2)", (ox + 25, oy - 45, oz), dict(material="ABS", qty=2))

        base, cap = build_egg_halves()
        for i, (name, th) in enumerate(E['STATES']):
            log("Egg state %s (%g deg)" % (name, th))
            lay = layer(name, (255, 160, 30))
            for sub, egg in egg_state(base, cap, th):
                add(egg, lay, name + "_" + sub, (0, i * E['STATE_DY'], 0), dict(open_deg=th))
                if th == 0:
                    sect = diff(egg, [box(-60, 60, -40, 0, -10, 60)], "section cut")  # Front view looks inside
                    add(sect, layer("Egg_Closed_Section", (255, 200, 120)), "Egg_Closed_Section_" + sub,
                        (0, -E['STATE_DY'], 0))
        lk = layer("Packed_In_Egg", (240, 80, 150))
        for nm, b in zip(["P1_wing_R", "P2_wing_L", "P3_clip_1", "P3_clip_2"], pack_in_egg(parts)):
            add(b, lk, "packed_" + nm)
            add(b, lk, "packed_" + nm + "_section", (0, -E['STATE_DY'], 0))
        if DEBUG:
            ld = layer("_Debug", (255, 0, 0))
            for b in DEBUG:
                add(b, ld, "failed boolean operand")
        doc.Views.Redraw()
        fails = [m for m in LOG if m.strip().startswith("!!")]
        print("---- done: %d warnings%s" % (len(fails), "" if not fails else " (see above)"))

    if __name__ == "__main__":
        main()
