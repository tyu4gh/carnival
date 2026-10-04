# -*- coding: utf-8 -*-
"""
Kinder Surprise toy: realistic seated gorilla, 3 snap-together ABS parts, built in Blender.

Run it in Blender 4.2+ / 5.x:
    Scripting workspace -> Open -> gorilla_blender_build.py -> Run Script
or headless:
    blender -b -P gorilla_blender_build.py -- --out /path/to/folder
(It also runs with the `bpy` Python module.)

Everything is parametric (P below). A run rebuilds the collections "Gorilla_*" from scratch.

Parts (all injection-moulded ABS, no metal, every connector points along Y = the mould's pull):
    P1 BODY  - back, shoulders, belly, haunches and legs; hollow from below (even wall).
               On its front: a peg and two slots (above / below the peg).
    P2 ARMS  - both arms joined by a thin chest strap; the strap has a hole and hangs on the peg.
    P3 HEAD  - head + neck; on its back: two tabs (into the slots), a socket for the peg tip and
               a channel the strap sits in. Pushing the head on clamps the arms - done.
The parts are cut out of one continuous sculpt, so the joints are only thin lines.

Frame: millimetres, Z up, the gorilla looks towards -Y, X = its left-right.
"""
import math
import sys
import os
import bpy
import bmesh
from mathutils import Vector, Matrix, Quaternion, noise
from mathutils.bvhtree import BVHTree

# =====================================================================================
# PARAMETERS
# =====================================================================================
P = dict(
    SCALE=0.70,          # sculpt scale (the sculpt below is drawn ~35 mm tall -> ~24 mm)
    VOXEL=0.13,          # remesh voxel size (mm) - surface detail resolution
    META_RES=0.25,       # metaball polygonisation size (mm)
    SMOOTH=6,            # smoothing iterations after remesh (generic)
    SMOOTH_BODY=14, SMOOTH_HEAD=6, SMOOTH_ARMS=10,   # blend softness of the sculpt per part
    # fur: streaky noise along the hair flow (displacement along the normal)
    FUR_AMP=0.10, FUR_FREQ=3.2, FUR_STRETCH=0.16, FUR_FINE=0.035,
    FACE_SMOOTH=True,    # bare skin on the face (no fur displacement there)
    # split between the parts (sculpt coordinates, scaled with SCALE)
    YF=-1.0,             # head / body contact plane (the neck)
    ZP=22.5,             # height of the peg and the chest strap
    # connectors (final millimetres, NOT scaled)
    BAND_H=3.0,          # chest strap height
    BAND_T=1.6,          # chest strap thickness (centred on YF)
    CLR=0.10,            # clearance between parts
    PEG_R=1.0,           # peg on the body (D 2.0)
    PEG_TIP=2.2,         # peg reaches this far into the head
    HOLE_CLR=0.10,       # strap hole = peg + this (strap slides on easily)
    SOCKET_GRIP=0.03,    # head socket = peg - this (light press fit)
    TAB_W=3.0, TAB_H=1.4, TAB_L=2.6,   # head tabs (into the body slots)
    TAB_DZ=2.55,         # tab centres above / below ZP
    SLOT_CLR=0.06,       # slot = tab + this, all round
    BUMP=0.08,           # snap bumps on the tabs (interference)
    LEAD=0.3,            # lead-in chamfer on peg and tabs
    # body coring (open at the bottom, core pulled downwards) - sculpt coordinates
    CAVITY=dict(co=(0.0, 3.0, 0.0), r=(7.3, 5.8, 14.0)),
    WALL_MIN=1.2,
    # packing in the closed capsule (filled in from pack_check.py): part, euler deg, offset
    PACK=None,
)

# ---------------- sculpt: metaball elements (centre, surface half-extents, rotation) ----------
# ELLIPSOID: surface half-extents = 0.574 x radius x size  ->  we give the half-extents directly
K_MB = 0.574


def E(co, r, rot=(0, 0, 0), stiff=2.0):
    return dict(type='ELLIPSOID', co=co, r=r, rot=rot, s=stiff)


def C(p0, p1, rad, rad1=None, stiff=2.0):
    """tapered capsule from p0 (radius rad) to p1 (radius rad1)"""
    return dict(type='CAPSULE', p0=p0, p1=p1, rad=rad, rad1=rad if rad1 is None else rad1, s=stiff)


def body_elems():
    el = [E((0, 1.8, 16.5), (10.2, 8.6, 10.8)),          # chest / torso
          E((0, 3.4, 22.6), (11.6, 7.4, 5.6)),           # shoulder hump (silverback)
          E((0, 6.2, 18.5), (8.6, 4.8, 8.4)),            # back
          E((0, 4.2, 25.5), (7.0, 4.6, 3.4)),            # upper back behind the neck
          E((0, -3.0, 16.0), (7.4, 4.6, 6.0)),           # pectorals
          E((0, -2.6, 9.4), (8.2, 7.2, 6.6)),            # belly
          E((0, 3.8, 4.4), (10.4, 8.6, 6.4)),            # rump
          E((0, 3.0, 1.0), (9.6, 8.8, 2.6))]             # haunches resting on the ground: broad flat seat
    for s in (-1, 1):
        el += [E((s * 4.0, -4.6, 17.6), (3.8, 2.6, 3.2)),                         # pectoral mass
               E((s * 7.0, -4.2, 5.0), (4.7, 7.6, 4.4), rot=(0, 0, s * -8)),      # thigh
               E((s * 7.8, -8.0, 5.9), (3.2, 3.0, 3.1)),                         # knee
               C((s * 7.9, -8.2, 4.8), (s * 8.3, -11.0, 2.4), 2.6, 2.3),          # shin
               E((s * 8.4, -11.4, 1.7), (3.8, 4.4, 1.9), rot=(0, 0, s * -6)),     # foot
               E((s * 5.2, -13.0, 1.5), (1.2, 1.7, 1.1), rot=(0, 0, s * 30))]     # big toe
        for dx in (-2.0, -0.65, 0.65, 2.0):                                       # toes
            el.append(E((s * 8.6 + dx, -15.2 + abs(dx) * 0.3, 1.25), (0.9, 1.05, 0.95)))
    return el


def head_elems():
    el = [E((0, -1.6, 23.0), (6.4, 5.8, 5.4)),            # neck (reaches back into the body)
          E((0, -4.6, 27.4), (5.7, 5.8, 5.5)),            # cranium
          E((0, -3.2, 31.4), (2.3, 4.8, 3.0)),            # sagittal crest (tall silverback head)
          E((0, -10.2, 28.7), (5.8, 2.4, 1.9)),           # brow ridge (heavy, overhanging)
          E((0, -10.0, 26.1), (3.9, 2.3, 2.4)),           # mid face
          E((0, -12.5, 25.5), (3.0, 1.6, 1.9)),           # broad flat nose
          E((0, -12.1, 23.3), (4.9, 3.0, 2.0)),           # upper lip / muzzle (protruding)
          E((0, -10.8, 21.6), (4.4, 2.8, 1.7)),           # lower jaw / chin
          E((0, -7.0, 22.6), (5.6, 3.6, 2.4))]            # jaw sides
    for s in (-1, 1):
        el += [E((s * 5.6, -4.6, 26.0), (0.8, 1.4, 1.6)),  # ear
               E((s * 4.0, -8.4, 24.6), (2.2, 2.6, 2.6)),  # cheek
               E((s * 3.0, -9.8, 28.9), (2.6, 1.8, 1.4), rot=(0, 0, s * 12))]   # brow sides
    return el


def arm_elems():
    el = []
    for s in (-1, 1):
        el += [E((s * 11.0, -1.0, 22.6), (4.6, 4.6, 4.4)),                        # shoulder / deltoid
               C((s * 11.9, -2.4, 20.6), (s * 12.9, -5.8, 13.0), 3.6, 2.9),        # upper arm
               E((s * 12.4, -5.0, 17.4), (2.6, 2.4, 3.6), rot=(s * 18, 0, 0)),    # biceps
               E((s * 13.2, -6.4, 12.4), (3.0, 3.0, 3.0)),                        # elbow
               C((s * 13.1, -6.8, 11.6), (s * 12.7, -10.2, 4.4), 3.5, 2.6),        # forearm (thick)
               E((s * 13.2, -7.6, 10.2), (3.4, 3.0, 3.4)),                        # forearm muscle
               C((s * 12.7, -10.2, 4.6), (s * 12.6, -11.0, 2.6), 2.5, 2.6),        # wrist
               E((s * 12.6, -11.5, 1.9), (3.4, 2.6, 1.9))]                        # hand (knuckle walking)
        for dx in (-2.1, -0.7, 0.7, 2.1):                                          # knuckles
            el.append(E((s * 12.6 + dx, -13.6, 1.6), (0.9, 1.0, 1.1)))
        el.append(E((s * 15.2, -11.2, 2.0), (0.9, 1.5, 1.0)))                     # thumb
    return el


# =====================================================================================
# helpers
# =====================================================================================
def log(*a):
    print("[gorilla]", *a)
    sys.stdout.flush()


def collection(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def clear_previous():
    for c in [c for c in bpy.data.collections if c.name.startswith("Gorilla_")]:
        for o in list(c.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(c)
    for blocks in (bpy.data.meshes, bpy.data.metaballs, bpy.data.materials, bpy.data.curves):
        for b in list(blocks):
            if b.users == 0:
                blocks.remove(b)


WORK = None


def link(ob, coll=None):
    (coll or WORK).objects.link(ob)
    return ob


def metaball_mesh(name, elems):
    """metaball elements -> mesh object (polygonised)"""
    mb = bpy.data.metaballs.new("MB_" + name)
    mb.resolution = P['META_RES']
    mb.render_resolution = P['META_RES']
    mb.threshold = 0.6
    ob = link(bpy.data.objects.new("MB_" + name, mb))
    k = P['SCALE']
    for d in elems:
        d = dict(d)
        for key in ('co', 'r', 'p0', 'p1'):
            if key in d:
                d[key] = tuple(c * k for c in d[key])
        if 'rad' in d:
            d['rad'] *= k
        e = mb.elements.new(type=d['type'])
        e.stiffness = d['s']
        if d['type'] == 'ELLIPSOID':
            e.co = Vector(d['co'])
            e.radius = 1.0 / K_MB
            e.size_x, e.size_y, e.size_z = d['r']
            rx, ry, rz = [math.radians(a) for a in d['rot']]
            e.rotation = (Matrix.Rotation(rz, 3, 'Z') @ Matrix.Rotation(ry, 3, 'Y') @
                          Matrix.Rotation(rx, 3, 'X')).to_quaternion()
        else:
            p0, p1 = Vector(d['p0']), Vector(d['p1'])
            e.co = (p0 + p1) / 2
            e.radius = d['rad'] / K_MB
            e.size_x = (p1 - p0).length / 2
            e.rotation = Vector((1, 0, 0)).rotation_difference((p1 - p0).normalized())
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.metaballs.remove(mb)
    return link(bpy.data.objects.new(name, me))


def shape_mesh(name, elems, smooth):
    """union of ellipsoids / capsules (scaled by SCALE) -> voxel remesh (= union) -> smoothing.
    `smooth` = smoothing iterations: more for soft fleshy blends, less for crisp features."""
    k = P['SCALE']
    bm = bmesh.new()
    for d in elems:
        tmp = bmesh.new()
        if d['type'] == 'ELLIPSOID':
            bmesh.ops.create_uvsphere(tmp, u_segments=24, v_segments=14, radius=1.0)
            bmesh.ops.scale(tmp, vec=Vector(d['r']) * k, verts=tmp.verts)
            rx, ry, rz = [math.radians(a) for a in d['rot']]
            R = Matrix.Rotation(rz, 4, 'Z') @ Matrix.Rotation(ry, 4, 'Y') @ Matrix.Rotation(rx, 4, 'X')
            bmesh.ops.transform(tmp, matrix=R, verts=tmp.verts)
            bmesh.ops.translate(tmp, vec=Vector(d['co']) * k, verts=tmp.verts)
        else:
            p0, p1 = Vector(d['p0']) * k, Vector(d['p1']) * k
            r0 = d['rad'] * k
            r1 = d.get('rad1', d['rad']) * k
            ax = p1 - p0
            n = max(2, int(ax.length / (0.35 * min(r0, r1))) + 1)
            for i in range(n + 1):                      # chain of spheres = smooth tapered capsule
                t = i / n
                one = bmesh.new()
                bmesh.ops.create_uvsphere(one, u_segments=20, v_segments=12, radius=r0 + (r1 - r0) * t)
                bmesh.ops.translate(one, vec=p0 + ax * t, verts=one.verts)
                m1 = bpy.data.meshes.new("tmp1")
                one.to_mesh(m1)
                one.free()
                tmp.from_mesh(m1)
                bpy.data.meshes.remove(m1)
        me = bpy.data.meshes.new("tmp")
        tmp.to_mesh(me)
        tmp.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new(name, me))
    return remesh(ob, smooth=smooth)


def apply_mods(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return ob


def remesh(ob, voxel=None, smooth=None):
    m = ob.modifiers.new("remesh", 'REMESH')
    m.mode = 'VOXEL'
    m.voxel_size = voxel or P['VOXEL']
    m.adaptivity = 0.0
    apply_mods(ob)
    if smooth if smooth is not None else P['SMOOTH']:
        s = ob.modifiers.new("smooth", 'LAPLACIANSMOOTH')
        s.iterations = smooth if smooth is not None else P['SMOOTH']
        s.lambda_factor = 0.5
        s.use_volume_preserve = True
        apply_mods(ob)
    return ob


def _bool_once(a, b, op, solver):
    m = a.modifiers.new("bool", 'BOOLEAN')
    m.operation = op
    m.object = b
    try:
        m.solver = solver
    except TypeError:
        return False
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(a.evaluated_get(dg))
    a.modifiers.clear()
    ok = len(me.vertices) > 0 or op == 'INTERSECT'
    if ok:
        old = a.data
        a.data = me
        if old.users == 0:
            bpy.data.meshes.remove(old)
    else:
        bpy.data.meshes.remove(me)
    return ok


def boolean(a, b, op, keep_b=False):
    """a = a (op) b. Manifold solver (Blender 4.5+, fast) with the exact solver as fallback:
    a result that loses (almost) the whole part is rejected and redone exactly."""
    v0, vb = volume(a), volume(b)
    tol = 0.02 * max(v0, 1.0) + 0.5
    done = False
    for solver in ('MANIFOLD', 'EXACT'):
        before = a.data.copy()
        if _bool_once(a, b, op, solver):
            v1 = volume(a)
            if op == 'DIFFERENCE':
                sane = v0 - vb - tol <= v1 <= v0 + tol
            elif op == 'UNION':
                sane = max(v0, vb) - tol <= v1 <= v0 + vb + tol
            else:
                sane = v1 <= min(v0, vb) + tol
            if sane:
                done = True
                bpy.data.meshes.remove(before)
                break
            log("  .. %s %s <- %s with %s gave an implausible result (%.1f, cutter %.1f -> %.1f mm3), retrying"
                % (op, a.name, b.name, solver, v0, vb, v1))
        old = a.data
        a.data = before
        if old.users == 0:
            bpy.data.meshes.remove(old)
    if not done:
        log("  !! boolean %s %s <- %s failed" % (op, a.name, b.name))
    if not keep_b:
        me = b.data
        bpy.data.objects.remove(b, do_unlink=True)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    return a


def copy(ob, name):
    c = ob.copy()
    c.data = ob.data.copy()
    c.name = name
    return link(c)


def box(name, x0, x1, y0, y1, z0, z1):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(x1 - x0, y1 - y0, z1 - z0), verts=bm.verts)
    bmesh.ops.translate(bm, vec=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def cylinder_y(name, x, z, r, y0, y1, seg=48, lead=0.0):
    """cylinder along Y from y0 to y1 (lead-in chamfer at the y1 end)"""
    bm = bmesh.new()
    rings = [(y0, r), (y1 - lead, r), (y1, r - lead)] if lead > 0 else [(y0, r), (y1, r)]
    loops = []
    for (y, rr) in rings:
        loops.append([bm.verts.new((x + rr * math.cos(2 * math.pi * i / seg), y,
                                    z + rr * math.sin(2 * math.pi * i / seg))) for i in range(seg)])
    for a, b in zip(loops, loops[1:]):
        for i in range(seg):
            bm.faces.new((a[i], a[(i + 1) % seg], b[(i + 1) % seg], b[i]))
    bm.faces.new(loops[0][::-1])
    bm.faces.new(loops[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def sphere(name, co, r, scale=(1, 1, 1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=r)
    bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    bmesh.ops.translate(bm, vec=co, verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def ellipsoid_dome(name, co, r, seg=48, rings=24):
    """half ellipsoid (z >= co.z) closed by a flat base, extended 1 mm below (opens the cavity)"""
    bm = bmesh.new()
    cx, cy, cz = co
    loops = []
    for j in range(rings + 1):
        t = (math.pi / 2) * j / rings
        z = cz + r[2] * math.sin(t)
        k = math.cos(t)
        if j == rings:
            break
        loops.append([bm.verts.new((cx + r[0] * k * math.cos(2 * math.pi * i / seg),
                                    cy + r[1] * k * math.sin(2 * math.pi * i / seg), z)) for i in range(seg)])
    top = bm.verts.new((cx, cy, cz + r[2]))
    base = [bm.verts.new((v.co.x, v.co.y, cz - 1.0)) for v in loops[0]]
    for a, b in zip(loops, loops[1:]):
        for i in range(seg):
            bm.faces.new((a[i], a[(i + 1) % seg], b[(i + 1) % seg], b[i]))
    for i in range(seg):
        bm.faces.new((loops[-1][i], loops[-1][(i + 1) % seg], top))
        bm.faces.new((base[(i + 1) % seg], base[i], loops[0][i], loops[0][(i + 1) % seg]))
    bm.faces.new(base[::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def offset_copy(ob, name, d):
    """grow (d > 0) / shrink a closed mesh along its normals, then remesh to keep it clean"""
    c = copy(ob, name)
    m = c.modifiers.new("disp", 'DISPLACE')
    m.strength = d
    m.mid_level = 0.0
    m.direction = 'NORMAL'
    apply_mods(c)
    return remesh(c, voxel=max(P['VOXEL'], 0.2), smooth=0)


def fur(ob, flow=(0, 0, 1), face_mask=None):
    """streaky noise displacement along the normals: fur strands following `flow`"""
    me = ob.data
    flow = Vector(flow).normalized()
    a = flow.orthogonal().normalized()
    b = flow.cross(a)
    f, st = P['FUR_FREQ'], P['FUR_STRETCH']
    for v in me.vertices:
        p = v.co
        q = Vector((p.dot(a) * f, p.dot(b) * f, p.dot(flow) * f * st))
        d = P['FUR_AMP'] * noise.noise(q) + P['FUR_FINE'] * noise.noise(q * 3.1)
        if face_mask is not None:
            d *= face_mask(p)
        v.co = p + v.normal * d
    me.update()


def face_mask(p):
    """bare skin on the face: no fur on the front of the muzzle / around the eyes"""
    if not P['FACE_SMOOTH']:
        return 1.0
    k = P['SCALE']
    t = max(0.0, min(1.0, (-p.y / k - 8.3) / 1.6))      # 0 behind, 1 on the face front
    zf = max(0.0, min(1.0, (29.2 - p.z / k) / 1.0))
    return 1.0 - t * zf


def volume(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = bm.calc_volume(signed=False)
    bm.free()
    return v


def overlap_volume(a, b):
    ca = copy(a, "tmp_a")
    cb = copy(b, "tmp_b")
    boolean(ca, cb, 'INTERSECT')
    v = volume(ca) if len(ca.data.vertices) else 0.0
    bpy.data.objects.remove(ca, do_unlink=True)
    return v


def material(name, rgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    if nt is not None:
        for n in nt.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                n.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
                n.inputs["Roughness"].default_value = 0.6
    return m


# =====================================================================================
# build
# =====================================================================================
FACE = dict(
    eye_socket=((2.1, -10.9, 27.05), 0.95, (1.15, 0.9, 0.7)),    # deep-set under the brow
    eye=((2.1, -10.45, 27.0), 0.55),
    nostril=((1.15, -14.05, 24.95), 0.68, (1.35, 1.0, 0.8)),      # big flared nostrils
    mouth=((0, -14.95, 22.5), 1.0, (3.9, 0.55, 0.22)),
)


def sculpt():
    """the three full shapes (before splitting): crisp head, softer body, muscular arms"""
    global WORK
    if WORK is None:
        WORK = collection("Gorilla_work")
    k = P['SCALE']

    def K3(v):
        return tuple(c * k for c in v)
    log("sculpt: primitives -> voxel union -> smoothing -> fur")
    body_full = shape_mesh("body_full", body_elems(), P['SMOOTH_BODY'])
    head_full = shape_mesh("head_full", head_elems(), P['SMOOTH_HEAD'])
    arms_full = shape_mesh("arms_full", arm_elems(), P['SMOOTH_ARMS'])
    fur(body_full, flow=(0, 0.25, 1))
    fur(arms_full, flow=(0, 0.35, 1))
    fur(head_full, flow=(0, 0.6, 1), face_mask=face_mask)
    for ob in (body_full, arms_full):          # flat bottom (after the fur): haunches, feet, knuckles
        boolean(ob, box("floor", -40, 40, -40, 40, -10, 0.0), 'DIFFERENCE')
    log("face details")
    F = FACE
    for s in (-1, 1):
        c, r, sc_ = F['eye_socket']
        boolean(head_full, sphere("socket", K3((s * c[0], c[1], c[2])), r * k, sc_), 'DIFFERENCE')
        c, r, sc_ = F['nostril']
        boolean(head_full, sphere("nostril", K3((s * c[0], c[1], c[2])), r * k, sc_), 'DIFFERENCE')
    for s in (-1, 1):
        c, r = F['eye']
        boolean(head_full, sphere("eye", K3((s * c[0], c[1], c[2])), r * k), 'UNION')
    c, r, sc_ = F['mouth']
    boolean(head_full, sphere("mouth", K3(c), r * k, sc_), 'DIFFERENCE')
    return body_full, head_full, arms_full
def build():
    global WORK
    clear_previous()
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 0.001
    sc.unit_settings.length_unit = 'MILLIMETERS'
    WORK = collection("Gorilla_work")
    k = P['SCALE']
    YF, ZP, BT, BH, CLR = P['YF'] * k, P['ZP'] * k, P['BAND_T'], P['BAND_H'], P['CLR']

    # ---- 1. sculpt the three full shapes ------------------------------------------------
    body_full, head_full, arms_full = sculpt()
    def K3(v):
        return tuple(c * k for c in v)

    # ---- 3. split into the three parts --------------------------------------------------
    log("split into parts")
    band = box("band", -40, 40, YF - BT / 2, YF + BT / 2, ZP - BH / 2, ZP + BH / 2)
    # arms = arms + the strap cut out of the chest / neck (outer surface = the sculpt itself)
    trunk = copy(body_full, "trunk")
    boolean(trunk, copy(head_full, "hf"), 'UNION')
    strap = copy(band, "strap")
    boolean(strap, trunk, 'INTERSECT', keep_b=True)
    arms = copy(arms_full, "P2_ARMS")
    boolean(arms, strap, 'UNION')
    # head = the sculpted head in front of the contact plane
    head = copy(head_full, "P3_HEAD")
    boolean(head, box("front", -40, 40, -60, YF, -10, 60), 'INTERSECT')
    # body = everything else (the neck behind the plane belongs to the body)
    body = trunk
    body.name = "P1_BODY"
    cut_head = offset_copy(head, "head_clr", CLR)
    boolean(body, cut_head, 'DIFFERENCE')
    boolean(body, offset_copy(arms, "arms_clr", CLR), 'DIFFERENCE')
    boolean(head, offset_copy(arms, "arms_clr2", CLR), 'DIFFERENCE')   # strap channel in the head
    boolean(body, box("band_clr", -40, 40, YF - BT / 2 - CLR, YF + BT / 2 + CLR,
                      ZP - BH / 2 - CLR, ZP + BH / 2 + CLR), 'DIFFERENCE')
    bpy.data.objects.remove(band, do_unlink=True)
    for o in (body_full, head_full, arms_full):
        bpy.data.objects.remove(o, do_unlink=True)

    # ---- 4. connectors -------------------------------------------------------------------
    log("connectors")
    r = P['PEG_R']
    y_floor = YF + BT / 2 + CLR                 # body face behind the strap
    peg = cylinder_y("peg", 0, ZP, r, y_floor + 1.5, YF - BT / 2 - P['PEG_TIP'], lead=P['LEAD'])
    boolean(body, peg, 'UNION')
    boolean(arms, cylinder_y("strap_hole", 0, ZP, r + P['HOLE_CLR'], YF + 3, YF - 3), 'DIFFERENCE')
    boolean(head, cylinder_y("socket", 0, ZP, r - P['SOCKET_GRIP'], YF - BT / 2 + 0.5,
                             YF - BT / 2 - P['PEG_TIP'] - 0.3), 'DIFFERENCE')
    tw, th, tl, dz, sc_ = P['TAB_W'], P['TAB_H'], P['TAB_L'], P['TAB_DZ'], P['SLOT_CLR']
    for sgn in (-1, 1):
        zc = ZP + sgn * dz
        tab = box("tab", -tw / 2, tw / 2, YF - 1.0, YF + tl - P['LEAD'], zc - th / 2, zc + th / 2)
        tip = box("tab_tip", -tw / 2 + P['LEAD'] / 2, tw / 2 - P['LEAD'] / 2, YF + tl - P['LEAD'] - 0.01,
                  YF + tl, zc - th / 2 + P['LEAD'] / 2, zc + th / 2 - P['LEAD'] / 2)
        boolean(tab, tip, 'UNION')
        for side in (-1, 1):                    # snap bumps on the top / bottom of the tab
            bump = cylinder_y("bump", 0, zc + side * (th / 2 - 0.35 + P['BUMP']), 0.35,
                              YF + tl - 1.6, YF + tl - 0.7, seg=24)
            bump.scale = (3.0, 1.0, 1.0)
            bump.location.x = 0
            apply_scale(bump)
            boolean(tab, bump, 'UNION')
        boolean(head, tab, 'UNION')
        boolean(body, box("slot", -tw / 2 - sc_, tw / 2 + sc_, YF - 1.0, YF + tl + 0.3,
                          zc - th / 2 - sc_, zc + th / 2 + sc_), 'DIFFERENCE')

    # ---- 5. hollow body (open at the bottom, core pulled downwards) ------------------------
    log("hollow body")
    cav = P['CAVITY']
    boolean(body, ellipsoid_dome("cavity", K3(cav['co']), K3(cav['r'])), 'DIFFERENCE')

    for ob in (body, arms, head):
        ob.data.validate()
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bad = sum(1 for e in bm.edges if not e.is_manifold)
        bm.free()
        if bad:          # a fallback boolean left open edges: one fine remesh makes it watertight
            log("  .. %s: %d non-manifold edges -> final remesh" % (ob.name, bad))
            remesh(ob, voxel=P['VOXEL'] * 0.8, smooth=0)
        cleanup(ob)
    return body, arms, head


def cleanup(ob):
    """remove boolean debris: degenerate faces and loose slivers - keep the main solid only"""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method='BEAUTY', ngon_method='BEAUTY')
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-3)      # 1 micron: sub-micron slivers
    bmesh.ops.dissolve_degenerate(bm, dist=1e-3, edges=bm.edges)
    seen_f, dup = {}, []
    for f in bm.faces:                     # double-sided zero-volume flaps: same vertices twice
        key = tuple(sorted(v.index for v in f.verts))
        if key in seen_f:
            dup += [f, seen_f[key]]
        else:
            seen_f[key] = f
    if dup:
        bmesh.ops.delete(bm, geom=list(set(dup)), context='FACES_ONLY')
        loose = [v for v in bm.verts if not v.link_faces]
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
        log("  .. %s: removed %d zero-volume flap faces" % (ob.name, len(set(dup))))
    bm.verts.ensure_lookup_table()
    seen, shells = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, shell = [v], []
        seen.add(v.index)
        while stack:
            x = stack.pop()
            shell.append(x)
            for e in x.link_edges:
                o = e.other_vert(x)
                if o.index not in seen:
                    seen.add(o.index)
                    stack.append(o)
        shells.append(shell)
    if len(shells) > 1:
        shells.sort(key=len, reverse=True)
        drop = [v for sh in shells[1:] for v in sh]
        bmesh.ops.delete(bm, geom=drop, context='VERTS')
        log("  .. %s: removed %d loose sliver(s)" % (ob.name, len(shells) - 1))
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def apply_scale(ob):
    me = ob.data
    me.transform(Matrix.Diagonal(Vector(ob.scale).to_4d()))
    ob.scale = (1, 1, 1)
    me.update()


# =====================================================================================
# checks, layout, export
# =====================================================================================
def report(body, arms, head):
    res = {}
    for ob in (body, arms, head):
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        nonman = sum(1 for e in bm.edges if not e.is_manifold)
        v = bm.calc_volume(signed=False)
        bm.free()
        bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        dims = [max(c[i] for c in bb) - min(c[i] for c in bb) for i in range(3)]
        res[ob.name] = dict(volume=round(v, 1), mass_g=round(v * 1.05e-3, 2), non_manifold_edges=nonman,
                            size=tuple(round(d, 1) for d in dims), verts=len(ob.data.vertices))
    res['overlap body/arms'] = round(overlap_volume(body, arms), 4)
    res['overlap body/head'] = round(overlap_volume(body, head), 4)
    res['overlap arms/head'] = round(overlap_volume(arms, head), 4)
    # wall thickness of the hollow body: the cavity grown by WALL_MIN must stay inside the body shell
    cav = P['CAVITY']
    w = P['WALL_MIN']
    k = P['SCALE']
    co, rr = tuple(c * k for c in cav['co']), tuple(c * k for c in cav['r'])
    grown = ellipsoid_dome("cav_grown", co, [x + w for x in rr])
    trunk_solid = copy(body, "trunk_solid")
    boolean(trunk_solid, ellipsoid_dome("cav_fill", co, rr), 'UNION')
    boolean(grown, box("above_floor", -40, 40, -40, 40, 0.0, 60), 'INTERSECT')
    boolean(grown, trunk_solid, 'DIFFERENCE')
    res['cavity wall < WALL_MIN (mm3 outside)'] = round(volume(grown) if len(grown.data.vertices) else 0.0, 3)
    bpy.data.objects.remove(grown, do_unlink=True)
    for k, v in res.items():
        log(k, v)
    return res


def layout(body, arms, head):
    """collections: assembled, exploded, parts; materials"""
    asm = collection("Gorilla_Assembled")
    exp = collection("Gorilla_Exploded")
    mats = {"P1_BODY": material("gorilla_body", (0.28, 0.27, 0.27)),
            "P2_ARMS": material("gorilla_arms", (0.33, 0.31, 0.30)),
            "P3_HEAD": material("gorilla_head", (0.22, 0.21, 0.21))}
    for ob in (body, arms, head):
        ob.data.materials.clear()
        ob.data.materials.append(mats[ob.name])
        for poly in ob.data.polygons:
            poly.use_smooth = True
        WORK.objects.unlink(ob)
        asm.objects.link(ob)
    off = {"P1_BODY": (60, 0, 0), "P2_ARMS": (60, -14, 0), "P3_HEAD": (60, -26, 4)}
    for ob in (body, arms, head):
        c = ob.copy()
        c.name = ob.name + "_exploded"
        c.location = off[ob.name]
        exp.objects.link(c)
    bpy.data.collections.remove(WORK)
    return asm


def export(body, arms, head, out):
    os.makedirs(out, exist_ok=True)
    for ob in (body, arms, head):
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        path = os.path.join(out, ob.name + ".stl")
        try:
            bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, global_scale=1.0,
                                  apply_modifiers=True)
        except Exception:
            bpy.ops.export_mesh.stl(filepath=path, use_selection=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "kinder_gorilla.blend"))
    log("exported to", out)


def main():
    out = None
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1:]
        if "--out" in args:
            out = args[args.index("--out") + 1]
    if bpy.app.background:      # headless: start from an empty scene (no default cube / camera)
        bpy.ops.wm.read_factory_settings(use_empty=True)
    body, arms, head = build()
    report(body, arms, head)
    layout(body, arms, head)
    if out:
        export(body, arms, head, out)


if __name__ == "__main__":
    main()
