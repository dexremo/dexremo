"""Render the zero pose and each joint moved on its own (+0.6 rad), labelled, into one sheet."""
import os, sys
os.environ.setdefault("MUJOCO_GL", "egl")
import mujoco, numpy as np
from PIL import Image, ImageDraw, ImageFont
m = mujoco.MjModel.from_xml_path(sys.argv[1]); d = mujoco.MjData(m)
m.geom_rgba[[i for i in range(m.ngeom) if m.geom_group[i] == 3]] = 0               # hide collision hulls
r = mujoco.Renderer(m, height=400, width=480)
# colour each link by its place in the finger so motion is easy to read
pal = {"tip": (0.97, 0.40, 0.03), "base": (0.30, 0.55, 0.92), "cmc1": (0.07, 0.65, 0.58), "cmc2": (0.96, 0.76, 0.07), "mcp": (0.07, 0.65, 0.58), "ip": (0.96, 0.76, 0.07)}
for g in range(m.ngeom):
    if m.geom_group[g] != 2: continue
    bn = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, m.geom_bodyid[g])
    key = next((k for k in pal if k in bn), "base"); m.geom_rgba[g] = (*pal[key], 1)
mujoco.mj_forward(m, d)
fb = [i for i in range(m.nbody) if any(k in (mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, i) or "") for k in ("cmc", "mcp", "ip", "tip"))]
cam = mujoco.MjvCamera(); cam.lookat[:] = d.xpos[fb].mean(0); cam.distance = 0.36; cam.azimuth = 150; cam.elevation = -14
f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
def shot(q, label):
    d.qpos[:] = q; mujoco.mj_forward(m, d); r.update_scene(d, cam); im = Image.fromarray(r.render())
    dr = ImageDraw.Draw(im); dr.rectangle((0, 0, 480, 34), fill=(20, 20, 20)); dr.text((10, 5), label, font=f, fill=(255, 200, 120)); return im
names = [mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, i) for i in range(m.njnt)]
tiles = [shot(np.zeros(m.nq), "zero pose")]
for i, n in enumerate(names):
    q = np.zeros(m.nq); q[m.jnt_qposadr[i]] = 0.6
    a = shot(np.zeros(m.nq), ""); b = shot(q, "%s  +0.6 rad (faint = zero)" % n)
    tiles.append(Image.blend(a, b, 0.7))
cols = 4; rows = (len(tiles) + cols - 1) // cols; sheet = Image.new("RGB", (cols * 480, rows * 400), "white")
for k, t in enumerate(tiles): sheet.paste(t, ((k % cols) * 480, (k // cols) * 400))
sheet.save(sys.argv[2]); print("saved", sys.argv[2], len(tiles))
