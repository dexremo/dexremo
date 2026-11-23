"""Figure of the fingertip force-sensor frame: (a) load-cell labels seen from outside, (b) side view with the axes and +/-Z loads.
Usage: DUMP_POSED=<dir> python build_model.py ... ; python sensor_axes_figure.py <posed parts dir> <build_info.json> <mjcf> <out.png>"""
import sys, glob, json
import numpy as np, trimesh, mujoco
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import FancyArrowPatch, Circle

POSED, INFO, MJCF, OUT = sys.argv[1:5]
F = "mid"
o = np.array(json.load(open(INFO))["origin"])
m = mujoco.MjModel.from_xml_path(MJCF); d = mujoco.MjData(m); mujoco.mj_forward(m, d)
s = m.site(F + "_force_site").id; p = d.site_xpos[s].copy(); n = d.site_xmat[s].reshape(3, 3)[:, 2].copy()
j = m.joint(F + "_ip").id; ax = d.xaxis[j].copy(); anc = d.xanchor[j].copy()

def load(f):
    t = trimesh.load(f); t.apply_translation(-o); return t
parts = {f: load(f) for f in sorted(glob.glob(POSED + "/*.stl"))}
near = lambda t: np.linalg.norm(t.centroid - p)
cells = sorted([t for f, t in parts.items() if "tension" in f], key=near)[:3]
plates = sorted([t for f, t in parts.items() if "layer1" in f], key=near)[:2]
nail = min([t for f, t in parts.items() if "nail" in f], key=near)
link = min([t for f, t in parts.items() if "fingertip_joints" in f], key=near)
servo = min([t for f, t in parts.items() if "STS3215" in f], key=near)
ip_br = min([t for f, t in parts.items() if "IP_joints" in f], key=near)

ctr = np.mean([c.centroid for c in cells], 0)
inpl = [(c.centroid - ctr) - np.dot(c.centroid - ctr, n) * n for c in cells]
kx = [i for i in range(3) if abs(np.dot(inpl[i] / np.linalg.norm(inpl[i]), ax)) < 0.3][0]
ex = inpl[kx] / np.linalg.norm(inpl[kx]); ey = np.cross(n, ex)
B = np.stack([ex, ey, n])                       # rows: sensor X, Y, Z
toS = lambda v: (v - ctr) @ B.T * 1000          # mm, sensor frame
outer, inner = sorted(plates, key=lambda t: -np.dot(t.centroid - ctr, n))

COL = dict(cell="#e03131", plate="#7950f2", nail="#f76707", link="#e64980", servo="#343a40", br="#f5c211")

def polys(t, col, u, v, depth, alpha=1.0, light=None):
    V = toS(t.vertices); Fc = t.faces; N = t.face_normals @ B.T
    P = V[Fc][:, :, [u, v]]; z = V[Fc][:, :, depth].mean(1)
    L = np.array(light) / np.linalg.norm(light)
    sh = 0.55 + 0.45 * np.abs(N @ L)
    c = np.array(matplotlib.colors.to_rgb(col))
    cols = np.clip(c[None] * sh[:, None] + (1 - sh[:, None]) * 0.12, 0, 1)
    return [(zz, pp, np.r_[cc, alpha]) for zz, pp, cc in zip(z, P, cols)]

def draw(axh, items, flip_depth):
    items.sort(key=lambda x: x[0], reverse=flip_depth)
    pc = PolyCollection([i[1] for i in items], facecolors=[i[2] for i in items], edgecolors="none", antialiased=True)
    axh.add_collection(pc)

def arrow(axh, a, b, col, lw=2.4, ms=16, txt=None, toff=(0, 0), fs=15, style="-|>"):
    axh.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=ms, lw=lw, color=col, zorder=10))
    if txt: axh.text(b[0] + toff[0], b[1] + toff[1], txt, color=col, fontsize=fs, fontweight="bold", ha="center", va="center", zorder=11)

fig, (A, S_) = plt.subplots(1, 2, figsize=(13, 6.4), gridspec_kw=dict(width_ratios=[1, 1.15]))
fig.patch.set_facecolor("white")

# ---- (a) top view: looking down -Z onto the inner plate and the load cells; outer plate as outline
it = polys(inner, COL["plate"], 0, 1, 2, light=(0.3, 0.4, 1)) + sum([polys(c, COL["cell"], 0, 1, 2, light=(0.3, 0.4, 1)) for c in cells], [])
draw(A, it, False)
ov = toS(outer.vertices)
hull = trimesh.path.polygons.projected(outer, normal=n) if False else None
R_out = np.percentile(np.linalg.norm(ov[:, :2], axis=1), 99)
A.add_patch(Circle((0, 0), R_out, fill=False, ls=(0, (5, 4)), lw=1.4, color="#666", zorder=3))
names = {}
for i, c in enumerate(cells):
    q = toS(c.centroid)[:2]
    lab = "A   1+X" if i == kx else ("B   1+Y" if q[1] > 0 else "C   1−Y")
    names[i] = lab
    dirv = q / np.linalg.norm(q)
    pos = q + dirv * 10.5 + (np.array([0, -9.5]) if i == kx else 0)
    A.text(*pos, lab, fontsize=16, fontweight="bold", ha="center", va="center", color="#111",
           bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=COL["cell"], lw=1.6), zorder=12)
arrow(A, (0, 0), (27, 0), "#1c7ed6", txt="+X", toff=(4.2, 0))
arrow(A, (0, 0), (0, 25), "#2b8a3e", txt="+Y", toff=(-3.2, 2.4))
A.add_patch(Circle((0, 0), 1.6, fc="white", ec="#c92a2a", lw=2, zorder=11)); A.plot(0, 0, ".", color="#c92a2a", ms=6, zorder=12)
A.text(-3.4, -3.0, "+Z", color="#c92a2a", fontsize=15, fontweight="bold", ha="center", zorder=12)
A.set_aspect("equal"); A.set_xlim(-27, 34); A.set_ylim(-27, 30); A.axis("off")
A.set_title("(a)", fontsize=15, loc="left")

# ---- (b) side view: X right, Z up, looking along +Y
light = (0.4, -1, 0.6)
it = []
for t, k in [(servo, "servo"), (ip_br, "br"), (link, "link"), (inner, "plate"), (outer, "plate"), (nail, "nail")] + [(c, "cell") for c in cells]:
    it += polys(t, COL[k], 0, 2, 1, light=light)
draw(S_, it, True)
# axes at the sensor centre
arrow(S_, (0, 0), (34, 0), "#1c7ed6", txt="+X", toff=(5, 0))
arrow(S_, (0, 0), (0, 26), "#c92a2a", txt="+Z", toff=(-5, -2))
S_.add_patch(Circle((0, 0), 1.6, fc="white", ec="#2b8a3e", lw=2, zorder=11))
S_.plot([-1.1, 1.1], [-1.1, 1.1], color="#2b8a3e", lw=1.6, zorder=12); S_.plot([-1.1, 1.1], [1.1, -1.1], color="#2b8a3e", lw=1.6, zorder=12)
S_.text(-9, -5, "+Y", color="#2b8a3e", fontsize=15, fontweight="bold", ha="center", zorder=12, bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.85))
# loads at the tip: +Z pull, -Z press
tip = toS(d.site_xpos[m.site(F + "_tip_site").id])
tx, tz = tip[0], tip[2]
arrow(S_, (tx, tz + 4), (tx, tz + 22), "#c92a2a", lw=3, ms=20)
S_.text(tx + 3, tz + 15, "+Z\npull", color="#c92a2a", fontsize=13, fontweight="bold", ha="left", va="center")
arrow(S_, (tx - 16, tz + 24), (tx - 16, tz + 6), "#862e9c", lw=3, ms=20)
S_.text(tx - 19, tz + 15, "−Z\npress", color="#862e9c", fontsize=13, fontweight="bold", ha="right", va="center")
# finger curls towards +X (IP +q)
a2 = toS(anc)
S_.add_patch(FancyArrowPatch((14, tz - 2), (34, tz - 22), connectionstyle="arc3,rad=-0.35",
                             arrowstyle="-|>", mutation_scale=16, lw=2, color="#495057", zorder=9))
S_.text(30, tz - 4, "IP +q:\nfinger curls in", color="#495057", fontsize=12, ha="left", va="center")
V = np.vstack([toS(t.vertices) for t in [servo, ip_br, link, nail]])
S_.set_aspect("equal"); S_.set_xlim(-45, 58); S_.set_ylim(-30, tz + 28)
S_.axis("off"); S_.set_title("(b)", fontsize=15, loc="left")

plt.tight_layout(); fig.savefig(OUT, dpi=110, facecolor="white")
print("cells", names, "ip axis . Y =", round(float(np.dot(ax, ey)), 3), "tip z mm", round(tz, 1))
