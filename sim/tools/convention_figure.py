"""Joint sign convention figure: for each joint type of the middle finger, overlay -0.5 rad (blue), zero (grey) and +0.5 rad (orange).
The hand is drawn palm down, the way it is mounted on the arm.
Usage: python3 convention_figure.py <hand.xml> <out.png>"""
import os, sys
os.environ.setdefault("MUJOCO_GL", "egl")
import mujoco, numpy as np
from PIL import Image, ImageDraw, ImageFont
xml = open(sys.argv[1]).read().replace("../meshes", os.path.abspath(os.path.join(os.path.dirname(sys.argv[1]), "..", "meshes")))
# Turn the hand palm down (180 deg about x) by wrapping it in a mount body; the triad shows the base frame axes, turned with it.
xml = xml.replace("  <worldbody>", '  <visual><headlight diffuse="0.75 0.75 0.75" ambient="0.4 0.4 0.4"/></visual>\n'
  '  <asset><texture name="sky" type="skybox" builtin="gradient" rgb1="1 1 1" rgb2="0.88 0.9 0.93" width="256" height="256"/></asset>\n  <worldbody>\n'
  '  <body name="mount" quat="0 1 0 0">\n'
  '    <geom type="capsule" fromto="-0.15 -0.10 0.03 -0.10 -0.10 0.03" size="0.003" rgba="0.9 0.1 0.1 1" contype="0" conaffinity="0" group="2"/>\n'
  '    <geom type="capsule" fromto="-0.15 -0.10 0.03 -0.15 -0.05 0.03" size="0.003" rgba="0.1 0.7 0.1 1" contype="0" conaffinity="0" group="2"/>\n'
  '    <geom type="capsule" fromto="-0.15 -0.10 0.03 -0.15 -0.10 0.08" size="0.003" rgba="0.1 0.2 0.9 1" contype="0" conaffinity="0" group="2"/>', 1)
xml = xml.replace("  </worldbody>", "  </body>\n  </worldbody>", 1)
m = mujoco.MjModel.from_xml_string(xml); d = mujoco.MjData(m)
m.geom_rgba[[i for i in range(m.ngeom) if m.geom_group[i] == 3]] = 0
m.vis.scale.framelength = 0.9; m.vis.scale.framewidth = 0.04
W, H = 560, 560
m.vis.global_.offwidth, m.vis.global_.offheight = W, H
r = mujoco.Renderer(m, height=H, width=W)
opt = mujoco.MjvOption(); opt.frame = mujoco.mjtFrame.mjFRAME_NONE
GREY, BLUE, ORANGE = (0.62, 0.64, 0.68), (0.20, 0.45, 0.95), (0.98, 0.50, 0.08)
mount = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "mount")
vis = [g for g in range(m.ngeom) if m.geom_group[g] == 2 and m.geom_bodyid[g] not in (0, mount)]   # hand links, not the triad
bname = lambda g: mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, m.geom_bodyid[g])
def colour(finger_rgb):
    for g in vis: m.geom_rgba[g] = (*(finger_rgb if bname(g).startswith("mid_") else GREY), 1)
mujoco.mj_forward(m, d)
cam = mujoco.MjvCamera(); cam.lookat[:] = d.xpos[[i for i in range(m.nbody) if (mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, i) or "").startswith("mid_")]].mean(0)
cam.lookat[:] = (-0.06, 0.0, -0.13); cam.distance = 0.52; cam.azimuth = 65; cam.elevation = -12
def shot(qj, val, rgb):
    d.qpos[:] = 0
    if qj is not None: d.qpos[m.jnt_qposadr[qj]] = val
    colour(rgb); mujoco.mj_forward(m, d); r.update_scene(d, cam, opt); return Image.fromarray(r.render()).convert("RGB")
fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
fs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
DESC = {"mid_cmc1": "+ counter-clockwise, seen from above", "mid_cmc2": "sideways swing", "mid_mcp": "+ lifts the finger up", "mid_ip": "+ curls the fingertip up"}
tiles = []
z = shot(None, 0, GREY)
dr = ImageDraw.Draw(z); dr.rectangle((0, 0, W, 64), fill=(24, 26, 30))
dr.text((14, 6), "zero pose, palm down", font=fb, fill=(255, 255, 255)); dr.text((14, 38), "triad: x red, y green, z blue (base frame axes)", font=fs, fill=(200, 200, 200))
tiles.append(z)
for n in ["mid_cmc1", "mid_cmc2", "mid_mcp", "mid_ip"]:
    j = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)
    a, b, c = shot(j, -0.5, BLUE), shot(None, 0, GREY), shot(j, 0.5, ORANGE)
    im = Image.blend(Image.blend(a, b, 0.5), c, 0.5)
    dr = ImageDraw.Draw(im); dr.rectangle((0, 0, W, 64), fill=(24, 26, 30))
    dr.text((14, 6), n.replace("mid_", "*_"), font=fb, fill=(255, 255, 255)); dr.text((14, 38), DESC[n], font=fs, fill=(200, 200, 200))
    dr.text((W - 150, 8), "+0.5 rad", font=fs, fill=tuple(int(255 * v) for v in ORANGE)); dr.text((W - 150, 36), "-0.5 rad", font=fs, fill=tuple(int(255 * v) for v in BLUE))
    tiles.append(im)
sheet = Image.new("RGB", (len(tiles) * W, H), "white")
for k, t in enumerate(tiles): sheet.paste(t, (k * W, 0))
sheet.save(sys.argv[2]); print("saved", sys.argv[2])
