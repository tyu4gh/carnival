"""fast look at the sculpt only (no split / connectors): python sculpt_preview.py [voxel]"""
import sys, os, math, bpy
from mathutils import Vector
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "gorilla_blender_build.py")).read().replace('if __name__ == "__main__":\n    main()', '')
ns = {}
exec(src, ns)
P = ns['P']
P['VOXEL'] = float(sys.argv[1]) if len(sys.argv) > 1 else 0.2
bpy.ops.wm.read_factory_settings(use_empty=True)
ns['WORK'] = None
b, h, a = ns['sculpt']()
cols = {b.name: (0.30, 0.29, 0.28), h.name: (0.22, 0.21, 0.21), a.name: (0.34, 0.32, 0.31)}
for ob in (b, h, a):
    m = ns['material']("m_" + ob.name, cols[ob.name])
    ob.data.materials.append(m)
    for p in ob.data.polygons:
        p.use_smooth = True
sc = bpy.context.scene
sc.view_settings.view_transform = 'Standard'
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 12; sc.cycles.use_denoising = False
sc.render.resolution_x = sc.render.resolution_y = 520
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.92, 0.92, 0.94, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.35
for nm, loc, e in (("key", (-60, -80, 90), 3.5), ("fill", (80, -40, 40), 0.6), ("rim", (20, 90, 70), 2.0)):
    ld = bpy.data.lights.new(nm, 'SUN'); ld.energy = e; ld.angle = 0.15
    o = bpy.data.objects.new(nm, ld); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector((0, 0, 12)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
os.makedirs(os.path.join(HERE, "img"), exist_ok=True)
k = P['SCALE']
for name, tgt, d, o in (("s_front34", (0, -3, 12), (-0.8, -1.4, 0.5), 30), ("s_side", (0, -2, 12), (1, -0.05, 0.1), 30),
                        ("s_face", (0, -7, 18), (-0.35, -1, 0.12), 13), ("s_faceside", (0, -6, 18), (1, -0.2, 0.05), 13)):
    d = Vector(d).normalized(); cam.location = Vector(tgt) + d * 150
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler(); cd.ortho_scale = o * k / 0.7
    sc.render.filepath = os.path.join(HERE, "img", name + ".png"); bpy.ops.render.render(write_still=True)
from PIL import Image
ims = [Image.open(os.path.join(HERE, "img", n + ".png")).convert("RGB") for n in ("s_front34", "s_side", "s_face", "s_faceside")]
W = Image.new("RGB", (520 * 4, 520), "white")
for i, im in enumerate(ims):
    W.paste(im, (520 * i, 0))
W.save(os.path.join(HERE, "img", "sculpt_sheet.png"))
print("ok")
