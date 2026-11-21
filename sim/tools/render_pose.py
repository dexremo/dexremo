"""Render the hanging hand at q = 0 from a few viewpoints. Usage: python3 render_pose.py <scene.xml> <out.png>"""
import os, sys
os.environ.setdefault("MUJOCO_GL", "egl")
import mujoco, numpy as np
from PIL import Image, ImageDraw, ImageFont
m = mujoco.MjModel.from_xml_path(sys.argv[1]); d = mujoco.MjData(m)
m.geom_rgba[[i for i in range(m.ngeom) if m.geom_group[i] == 3]] = 0
pal = {"tip": (0.97, 0.40, 0.03), "cmc1": (0.07, 0.65, 0.58), "cmc2": (0.96, 0.76, 0.07), "mcp": (0.20, 0.22, 0.25), "ip": (0.96, 0.76, 0.07), "base": (0.30, 0.55, 0.92)}
for g in range(m.ngeom):
    if m.geom_group[g] != 2: continue
    bn = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, m.geom_bodyid[g]) or ""
    m.geom_rgba[g] = (*pal[next((k for k in pal if k in bn), "base")], 1)
W, H = 640, 640
m.vis.global_.offwidth, m.vis.global_.offheight = max(W, m.vis.global_.offwidth), max(H, m.vis.global_.offheight)
r = mujoco.Renderer(m, height=H, width=W); mujoco.mj_forward(m, d)
c = d.xpos[1:].mean(0)
f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
tiles = []
for az, el, lab in ((150, 8, "front"), (60, 8, "side"), (150, -60, "top")):
    cam = mujoco.MjvCamera(); cam.lookat[:] = c; cam.distance = 0.62; cam.azimuth = az; cam.elevation = el
    r.update_scene(d, cam); im = Image.fromarray(r.render())
    ImageDraw.Draw(im).text((14, 10), "q = 0  (%s)" % lab, font=f, fill=(30, 30, 30)); tiles.append(im)
sheet = Image.new("RGB", (W * len(tiles), H), "white")
for k, t in enumerate(tiles): sheet.paste(t, (k * W, 0))
sheet.save(sys.argv[2]); print("saved", sys.argv[2])
