"""Preview renders of out/kinder_gorilla.blend (Cycles, CPU). Usage: python render_previews.py"""
import math
import os
import sys
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
IMG = os.path.join(HERE, "img")
os.makedirs(IMG, exist_ok=True)
SAMPLES = int(os.environ.get("SAMPLES", "24"))

bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "kinder_gorilla.blend"))
sc = bpy.context.scene
sc.view_settings.view_transform = 'Standard'
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = False
sc.render.resolution_x, sc.render.resolution_y = 640, 640
sc.render.film_transparent = False
world = sc.world or bpy.data.worlds.new("w")
sc.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (0.92, 0.92, 0.94, 1.0)
bg.inputs[1].default_value = 0.35


def light(name, loc, energy, size=30):
    ld = bpy.data.lights.new(name, 'SUN')
    ld.energy = energy
    ld.angle = 0.15
    ob = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector((0, 0, 14)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return ob


light("key", (-60, -80, 90), 2.2, 60)
light("fill", (80, -40, 40), 0.6, 60)
light("rim", (20, 90, 70), 2.0, 60)
cam_d = bpy.data.cameras.new("cam")
cam_d.type = 'ORTHO'
cam = bpy.data.objects.new("cam", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam


def show(coll_names):
    for c in bpy.data.collections:
        if c.name.startswith("Gorilla_"):
            c.hide_render = c.name not in coll_names


def shot(name, target, direction, ortho, colls):
    show(colls)
    d = Vector(direction).normalized()
    cam.location = Vector(target) + d * 150
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    cam_d.ortho_scale = ortho
    sc.render.filepath = os.path.join(IMG, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("rendered", name)


A = ["Gorilla_Assembled"]
shot("g_front34", (0, -4, 12), (-0.8, -1.4, 0.55), 34, A)
shot("g_front", (0, -4, 12), (0, -1, 0.12), 32, A)
shot("g_side", (0, -2, 12), (1, -0.05, 0.1), 34, A)
shot("g_back34", (0, 0, 12), (0.9, 1.2, 0.6), 34, A)
shot("g_face", (0, -8, 18), (-0.35, -1, 0.15), 16, A)
shot("g_under", (0, -2, 8), (0.3, -0.5, -1.0), 34, A)
if bpy.data.collections.get("Gorilla_Exploded"):
    shot("g_exploded", (60, -12, 10), (-0.9, -1.3, 0.7), 46, ["Gorilla_Exploded"])
if bpy.data.collections.get("Gorilla_Packed"):
    shot("g_packed", (0, 0, 22), (1, -0.6, 0.25), 48, ["Gorilla_Packed"])
