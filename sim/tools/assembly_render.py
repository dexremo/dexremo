"""Render the assembly guide (with fasteners) from the assembly STEP files.
For each step: a still (new parts coloured, parts already in place grey, legend with counts), an exploded still and a GIF in
which the step's phases play one after another (e.g. nuts in, servo in, screws in).
Directions: a screw or nut leaves along its own axis, towards its head; any other part is slid along candidate axes through
a 1 mm voxel model of the parts already in place, and the direction with the least overlap is the way it goes in.
Usage: python3 assembly_render2.py <out dir> [step numbers...]"""
import json, os, sys
os.environ.setdefault("MUJOCO_GL", "egl")
import numpy as np, trimesh, mujoco
from PIL import Image, ImageDraw, ImageFont
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
ONLY = set(int(a) for a in sys.argv[2:])
HERE = os.path.dirname(os.path.abspath(__file__))

class Asm:
    def __init__(self, d):
        self.dir = os.path.join(HERE, d); self.P = json.load(open(os.path.join(self.dir, "parts.json")))
        self.M = {}; self.V = {}
    def mesh(self, i):
        if i not in self.M: self.M[i] = trimesh.load(os.path.join(self.dir, "parts", self.P[i]["file"]))
        return self.M[i]
    def part(self, i): return self.P[i]["part"]
    def vox(self, i):
        if i not in self.V: self.V[i] = np.round(self.mesh(i).voxelized(0.001).fill().points * 1000).astype(np.int32)
        return self.V[i]

FIN = Asm("v3/dexremo_hand_full_finger_assemble")
FNS = Asm("v3/dexremo_hand_full_no_sensor_finger_assemble")
CTL = Asm("v3/dexremo_controller_finger_assemble")
HAND = Asm("v2/dexremo_hand_full_assemble")

def label(name):
    if " gb_" not in name:
        return {"STS3215_03a.step": "ST3215 servo", "tension-sensor": "Load cell (0-5 kg)"}.get(name, name)
    if "M3X6" in name and "TYPE135" in name: return "M3x6 cheese-head screw"
    if "M3X6" in name: return "M3x6 countersunk screw"
    if "M3X12" in name: return "M3x12 cheese-head screw"
    if "M2.5X3" in name: return "M2.5x3 screw"
    if "ST2.2" in name: return "ST2.2x4.5 self-tapping screw"
    if "NUT" in name and "M3" in name: return "M3 hex nut"
    return name
is_fast = lambda A, i: " gb_" in A.part(i)
is_servo = lambda A, i: A.part(i).startswith("STS")

def fastener_axis(A, i):
    """Unit vector along the fastener's axis, pointing from its tip towards its head (for a nut: either way)."""
    m = A.mesh(i); v = m.vertices - m.centroid
    w, U = np.linalg.eigh(np.cov(v.T))
    k = int(np.argmax([abs(w[j] - np.mean(np.delete(w, j))) for j in range(3)]))     # the axis of symmetry
    a = U[:, k]; t = v @ a; r = np.linalg.norm(v - np.outer(t, a), axis=1)
    hi, lo = r[t > 0].max() if (t > 0).any() else 0, r[t < 0].max() if (t < 0).any() else 0
    return a if hi >= lo else -a

def overlap(A, ctx, mov, d):
    if not ctx: return 0
    C = np.vstack([A.vox(i) for i in ctx]); M = np.vstack([A.vox(i) for i in mov])
    lo = np.minimum(C.min(0), M.min(0)) - 80; dims = np.maximum(C.max(0), M.max(0)) + 80 - lo + 1
    G = np.zeros(dims, bool); G[tuple((C - lo).T)] = True
    Q = np.round(M + d).astype(np.int32) - lo; Q = Q[np.all((Q >= 0) & (Q < dims), axis=1)]
    return int(G[tuple(Q.T)].sum())

def insertion_dir(A, ctx, mov, extra=()):
    cands = [np.array(v, float) for v in np.vstack([np.eye(3), -np.eye(3)])] + [np.array(e, float) for e in extra]
    for i in list(ctx) + list(mov):
        if is_servo(A, i):
            s = np.array(A.P[i]["T"])[:3, :3] @ np.array([0, 0, 1.0]); cands += [s, -s]
            s = np.array(A.P[i]["T"])[:3, :3] @ np.array([1.0, 0, 0]); cands += [s, -s]
        if is_fast(A, i): a = fastener_axis(A, i); cands += [a, -a]
    uniq = []
    for c in cands:
        c = c / np.linalg.norm(c)
        if not any(np.dot(c, u) > 0.995 for u in uniq): uniq.append(c)
    near = [i for i in ctx if np.all(A.mesh(i).bounds[0] - 0.06 < np.vstack([A.mesh(j).bounds[1] for j in mov]).max(0))
            and np.all(A.mesh(i).bounds[1] + 0.06 > np.vstack([A.mesh(j).bounds[0] for j in mov]).min(0))]
    base = overlap(A, near, mov, np.zeros(3))
    cc = np.vstack([A.mesh(i).centroid for i in near]).mean(0) if near else np.zeros(3)
    mc = np.vstack([A.mesh(i).centroid for i in mov]).mean(0)
    best = None
    for u in uniq:
        score = sum(max(overlap(A, near, mov, u * s) - base, 0) for s in (3, 6, 10, 16, 24, 34))
        key = (score, -np.dot(u, (mc - cc) * 1000))
        if best is None or key < best[0]: best = (key, u)
    return best[1], best[0][0]

# ---------------- steps ----------------
# phase: dict(parts, dist mm, mode "auto" | "axis" | "show", label?, color?)
def ph(parts, dist=40, mode="auto", **kw): return dict(parts=list(parts), dist=dist, mode=mode, **kw)
scr = lambda parts, dist=14, **kw: ph(parts, dist, "axis", **kw)

# single finger, force-sensing version (indices from dexremo_hand_full_finger_assemble)
f = dict(housing=7, s1=6, nuts1=[68, 69, 70, 71], body1=[54, 55, 66, 67], cmc2=8, horn1=[28, 32, 33, 35], s2=0, body2=[52, 53, 56, 57],
         mcp=3, horn2=[29, 30, 31, 34, 39, 40, 41, 42], s3=2, horn3=[17, 18, 20, 22, 23, 36, 37, 38], ip=4, body3=[60, 61, 62, 63], m25=[45],
         s4=5, horn4=[15, 16, 19, 21, 24, 25, 26, 27], tip=1, body4=[58, 59, 64, 65],
         inner=14, nuts_in=[49, 50, 51], cells=[11, 12, 13], scr_in=[43, 44], outer=10, scr_out=[46, 47, 48], nail=9)
seq = lambda *keys: sum(([f[k]] if isinstance(f[k], int) else list(f[k]) for k in keys), [])
BASE = ["housing", "nuts1", "s1", "body1", "cmc2", "horn1", "s2", "body2", "mcp", "horn2", "s3", "horn3", "ip", "body3",
        "s4", "horn4", "tip", "body4"]          # m25 (a loose M2.5 on the IP link) is a CAD leftover, left out
upto = lambda k: seq(*BASE[:BASE.index(k)])
TIPSTACK = seq("inner", "nuts_in", "cells", "scr_in", "outer", "scr_out", "nail")
VF = (0, 10, 1.0)                     # default finger view (azimuth, elevation, zoom)
FINGER_STEPS = [
 ("CMC1 housing: hide the nuts", FIN, [], [ph([f["housing"]], 0, "show", name="CMC1_left_joint (left finger) / CMC1_mid_right_joint"), ph(f["nuts1"], 30)], (145, 20, 0.8, "flip_x")),
 ("CMC1 servo into the housing", FIN, upto("s1"), [ph([f["s1"]], 45), scr(f["body1"])], (-30, 25, 0.7)),
 ("CMC2 bracket onto the CMC1 servo horn", FIN, upto("cmc2"), [ph([f["cmc2"]], 40), scr(f["horn1"])], (-30, 25, 1.2)),
 ("CMC2 servo into the CMC2 bracket", FIN, upto("s2"), [ph([f["s2"]], 45), scr(f["body2"])], (-30, 20, 1.2)),
 ("MCP link onto the CMC2 servo horn", FIN, upto("mcp"), [ph([f["mcp"]], 40), scr(f["horn2"])], (-30, 15, 1.1)),
 ("MCP servo onto the MCP link", FIN, upto("s3"), [ph([f["s3"]], 45), scr(f["horn3"])], (-30, 15, 1.1)),
 ("IP link over the MCP servo", FIN, upto("ip"), [ph([f["ip"]], 40), scr(f["body3"])], (-30, 15, 1.0)),
 ("IP servo onto the IP link", FIN, upto("s4"), [ph([f["s4"]], 45), scr(f["horn4"])], (-30, 15, 1.0)),
 # the fingertip is built as a unit first (sensor sandwich, then the distal link from below), then fitted onto the IP servo
 ("Fingertip sensor: plates and load cells", FIN, [], [ph([f["inner"]], 0, "show", name="force_sensor_layer1 (inner plate)"),
   ph(f["nuts_in"], 0, "show", name="M3 hex nut, embedded while printing"), ph(f["cells"], 25), scr(f["scr_in"], count=3),
   ph([f["outer"]], 25, name="force_sensor_layer1 (outer plate)"), scr(f["scr_out"]), ph([f["nail"]], 35)], (-30, 15, 0.55)),
 ("Distal link onto the sensor", FIN, TIPSTACK, [ph([f["tip"]], 35)], (-30, 15, 1.7)),
 ("Fingertip onto the IP servo", FIN, upto("tip"), [ph([f["tip"]] + TIPSTACK, 45, name="Fingertip unit (steps 9-10)", count=1), scr(f["body4"])], (-30, 15, 1.0)),
]

# no-sensor fingertip: map the no-sensor finger by part name and position onto its own indices
def nsf():
    P = FNS.P; c = lambda i: (np.array(P[i]["bbox_min_mm"]) + np.array(P[i]["bbox_max_mm"])) / 2
    nail = [p["idx"] for p in P if p["part"] == "left_finger_nail"][0]
    tip = [p["idx"] for p in P if p["part"] == "fingertip_joints"][0]
    nuts = [p["idx"] for p in P if "NUT" in p["part"] and np.linalg.norm(c(p["idx"]) - c(nail)) < 40]
    return nail, nuts, tip
N_NAIL, N_NUTS, N_TIP = nsf()
NS_STEPS = [("No-sensor version: fingernail onto the distal link", FNS, [],
             [ph([N_TIP], 0, "show"), ph([N_NAIL], 35, carry=N_NUTS, name="left_finger_nail (nuts embedded while printing)")], (-30, 15, 0.75))]

# whole hand (indices from dexremo_hand_full_assemble). The STEP repeats the right finger's four palm screws once; drop the copies
# and the one loose screw that touches nothing.
def hand():
    P = HAND.P; c = lambda i: (np.array(P[i]["bbox_min_mm"]) + np.array(P[i]["bbox_max_mm"])) / 2
    one = lambda n: [p["idx"] for p in P if p["part"] == n][0]
    palm, conn, flange, arm, cam = one("hand-base"), one("hand_connector"), one("franka_flange"), one("hand_eye_cam_mount"), one("camera_mount")
    seen, skip = {}, set()
    for p in P:
        key = (p["part"], tuple(np.round(c(p["idx"]))))
        if key in seen: skip.add(p["idx"])
        seen[key] = p["idx"]
    fast = json.load(open(os.path.join(HAND.dir, "fasteners.json")))
    skip |= {int(k) for k, v in fast.items() if not v}
    housings = {"left": one("CMC1_left_joint")}
    for i in [p["idx"] for p in P if p["part"] == "CMC1_mid_right_joint"]:
        housings["mid" if c(i)[1] > 0 else "right"] = i
    fy = {k: c(i)[1] for k, i in housings.items()}
    palm_scr = {k: [] for k in fy}; fing = {k: [] for k in fy}
    for p in P:
        i = p["idx"]
        if i in skip or i in (palm, conn, flange, arm, cam): continue
        k = min(fy, key=lambda k: abs(c(i)[1] - fy[k]))
        (palm_scr if "M3X12" in p["part"] else fing)[k].append(i)
    return palm, conn, flange, arm, cam, fing, palm_scr
PALM, CONN, FLANGE, ARM, CAM, FING, PSCR = hand()
FINGER_COL = {"left": (0.25, 0.48, 0.90), "mid": (0.95, 0.45, 0.10), "right": (0.15, 0.62, 0.55)}
HOUSING = {"left": "CMC1_left_joint", "mid": "CMC1_mid_right_joint", "right": "CMC1_mid_right_joint"}
NAIL = {"left": "left_finger_nail", "mid": "mid_finger_nail", "right": "right_finger_nail"}
allf = lambda: sum((FING[k] for k in ("left", "mid", "right")), [])
allps = lambda: sum((PSCR[k] for k in ("left", "mid", "right")), [])
VH = (-15, 12, 0.7)
HAND_STEPS = [
 ("Build all three fingers", HAND, [], [ph(FING[k], 0, "show", label="%s finger: %s, %s" % (k.capitalize(), HOUSING[k], NAIL[k]), color=FINGER_COL[k])
                                       for k in ("left", "mid", "right")], (-15, 12, 0.7)),
 ("Screw the fingers onto the palm", HAND, [PALM], [ph(FING[k], 60, label="%s finger" % k.capitalize(), color=FINGER_COL[k]) for k in ("left", "mid", "right")]
  + [ph(allps(), 16, "axis")], VH),
 ("Hand connector", HAND, [PALM] + allf() + allps(), [ph([CONN], 50)], (135, -15, 1.5)),
 ("Franka flange adapter", HAND, [PALM, CONN] + allf() + allps(), [ph([FLANGE], 50)], (135, -15, 1.5)),
 ("Hand-eye camera mount (optional)", HAND, [PALM, CONN, FLANGE] + allf() + allps(), [ph([ARM], 60), ph([CAM], 60)], (120, -15, 1.1)),
]

def ctl():
    P = CTL.P; one = lambda n: [p["idx"] for p in P if p["part"] == n][0]
    return one("fingertip_joints"), one("controller_finger"), [p["idx"] for p in P if "NUT" in p["part"]], [p["idx"] for p in P if "M3X6" in p["part"]]
C_TIP, C_RING, C_NUTS, C_SCR = ctl()
CTL_STEPS = [("Leader device: ring fingertip onto the distal link", CTL, [],
              [ph([C_TIP], 0, "show"), ph([C_RING], 35, carry=C_NUTS, name="controller_finger (nuts embedded while printing)"),
               scr(C_SCR, 14)], (-35, -25, 1.05))]

STEPS = FINGER_STEPS + NS_STEPS + CTL_STEPS + HAND_STEPS

COLS = [(0.95, 0.45, 0.10), (0.15, 0.62, 0.55), (0.25, 0.48, 0.90), (0.75, 0.30, 0.65), (0.85, 0.25, 0.25)]
FCOL = {"M3x6 cheese-head screw": (0.10, 0.12, 0.55), "M3 hex nut": (0.55, 0.25, 0.80), "M3x6 countersunk screw": (0.92, 0.72, 0.10), "ST2.2x4.5 self-tapping screw": (0.85, 0.20, 0.20),
        "M2.5x3 screw": (0.10, 0.12, 0.55), "M3x12 cheese-head screw": (0.92, 0.72, 0.10)}
GREY = (0.76, 0.77, 0.79); SERVO = (0.18, 0.19, 0.22)
W, H = 900, 640; FR = 10

def scene_xml(A, items):
    a = ['<mujoco>', '<visual><global offwidth="%d" offheight="%d"/><headlight diffuse="0.62 0.62 0.62" ambient="0.4 0.4 0.4"/></visual>' % (W, H),
         '<asset><texture name="sky" type="skybox" builtin="gradient" rgb1="1 1 1" rgb2="0.9 0.91 0.93" width="64" height="64"/>']
    a += ['<mesh name="m%d" file="%s"/>' % (i, os.path.join(A.dir, "parts", A.P[i]["file"])) for i, _ in items]
    a += ['</asset><worldbody><light pos="0.3 -0.5 0.8" dir="-0.3 0.5 -0.8" diffuse="0.5 0.5 0.5"/>']
    a += ['<body name="b%d" mocap="true"><geom type="mesh" mesh="m%d" rgba="%.3f %.3f %.3f 1" contype="0" conaffinity="0"/></body>' % (i, i, *c) for i, c in items]
    return "\n".join(a + ['</worldbody></mujoco>'])
fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
fs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 19)
ease = lambda t: t * t * (3 - 2 * t)

def render(k, title, A, ctx, phases, view):
    colour, legend, offs, when, placed, ci = {}, [], {}, {}, list(ctx), 0
    ride, vis = {}, {}                                 # ride: extra offset a part carries until a later phase; vis: phase it appears in
    log = []
    for n, p in enumerate(phases):
        parts = p["parts"]
        if p["mode"] == "axis":
            for i in parts: offs[i] = fastener_axis(A, i) * p["dist"] / 1000; when[i] = n
        elif p["mode"] == "auto" and p["dist"]:
            host = p.get("host", placed)
            if p.get("host") is not None and len(parts) > 1 and all(is_fast(A, i) for i in parts):
                for i in parts:
                    u, sc = insertion_dir(A, host, [i]); offs[i] = u * p["dist"] / 1000; when[i] = n; log.append((A.part(i)[-12:], u.round(2), sc))
            else:
                carry = p.get("carry", [])
                u, sc = insertion_dir(A, [i for i in host if i not in carry], parts + carry)
                for i in parts: offs[i] = u * p["dist"] / 1000; when[i] = n
                for i in carry: ride[i] = (u * p["dist"] / 1000, n)
                if carry:  # carried parts already placed earlier make the carrier appear with them
                    for i in parts: vis[i] = min([when[c] for c in carry if c in when] or [n])
                log.append((label(A.part(parts[0]))[:24], u.round(2), sc))
        placed += parts
        if "color" in p:
            for i in parts: colour[i] = p["color"]
            legend.append([p["label"], p["color"], 0]); continue
        for i in p.get("carry", []): colour[i] = (0.55, 0.25, 0.80)
        for i in parts:
            key = p.get("name") or label(A.part(i)); L = next((L for L in legend if L[0] == key), None)
            if L is None:
                fc = next((v for k_, v in FCOL.items() if key.startswith(k_)), None)
                c = SERVO if is_servo(A, i) else fc or COLS[ci % len(COLS)]; ci += not (is_servo(A, i) or fc)
                L = [key, c, 0]; legend.append(L)
            colour[i] = L[1]; L[2] += 1
        if "count" in p: L[2] = p["count"]
    for l in log: print("   step %d  %-26s dir %s residual %d" % (k, *l))
    items = [(i, GREY) for i in ctx if i not in colour] + list(colour.items())
    m = mujoco.MjModel.from_xml_string(scene_xml(A, items)); d = mujoco.MjData(m)
    bid = {i: m.body("b%d" % i).mocapid[0] for i, _ in items}
    nph = max(len(phases), 1)
    gid = {i: m.body("b%d" % i).geomadr[0] for i, _ in items}
    # optional whole-scene turn for a clearer view: "flip_x" turns the scene upside down about the x axis
    C0 = np.vstack([A.mesh(i).bounds for i, _ in items]).mean(0)
    RV, QV = (np.diag([1.0, -1, -1]), np.array([0, 1.0, 0, 0])) if len(view) > 3 and view[3] == "flip_x" else (np.eye(3), np.array([1.0, 0, 0, 0]))
    def place(t):                                       # t in [0, nph]: phase n moves during [n, n+1]; later phases stay hidden
        for i, _ in items:
            pos = offs[i] * (1 - ease(np.clip(t - when[i], 0, 1))) if i in offs else np.zeros(3)
            if i in ride: pos = pos + ride[i][0] * (1 - ease(np.clip(t - ride[i][1], 0, 1)))
            d.mocap_pos[bid[i]] = RV @ pos + (C0 - RV @ C0)
            d.mocap_quat[bid[i]] = QV
            if i in when: m.geom_rgba[gid[i], 3] = 1.0 if t >= vis.get(i, when[i]) else 0.0
        mujoco.mj_forward(m, d)
    focus = list(colour) or [i for i, _ in items]
    pts = np.vstack([A.mesh(i).bounds for i in focus] + [A.mesh(i).bounds + offs[i] + (ride[i][0] if i in ride else 0) for i in offs])
    allp = np.vstack([A.mesh(i).bounds for i, _ in items])
    az, el, zoom = view[:3]
    cam = mujoco.MjvCamera(); cam.lookat[:] = 0.6 * (pts.min(0) + pts.max(0)) / 2 + 0.4 * (allp.min(0) + allp.max(0)) / 2
    cam.distance = max(np.linalg.norm(pts.max(0) - pts.min(0)), 0.6 * np.linalg.norm(allp.max(0) - allp.min(0))) * 1.5 * zoom
    cam.azimuth = az; cam.elevation = -el
    r = mujoco.Renderer(m, height=H, width=W)
    def frame(t):
        place(t); r.update_scene(d, cam); im = Image.fromarray(r.render()).convert("RGB")
        dr = ImageDraw.Draw(im); dr.rectangle((0, 0, W, 50), fill=(24, 26, 30)); dr.text((18, 11), "Step %d  %s" % (k, title), font=fb, fill=(255, 255, 255))
        y = 64
        for n_, c, q in legend:
            dr.rectangle((18, y + 3, 36, y + 21), fill=tuple(int(255 * v) for v in c), outline=(60, 60, 60))
            dr.text((46, y), n_ + ("  x%d" % q if q > 1 else ""), font=fs, fill=(30, 30, 30)); y += 30
        return im
    frame(nph).save(os.path.join(OUT, "step%02d.png" % k))
    if offs:
        frames = [frame(0)] * 5
        for n in range(nph):
            if any(when.get(i) == n for i in offs): frames += [frame(n + t) for t in np.linspace(0, 1, FR)] + [frame(n + 1)] * 3
        frames += [frame(nph)] * 9
        frames = [s.resize((W * 3 // 5, H * 3 // 5), Image.LANCZOS) for s in frames]
        strip = Image.new("RGB", (frames[0].width, frames[0].height * 3))   # palette from the start, middle and end frames
        for j, fr in enumerate((frames[0], frames[len(frames) // 2], frames[-1])): strip.paste(fr, (0, j * fr.height))
        pal = strip.quantize(255, method=2, dither=0)
        frames = [s.quantize(palette=pal, dither=0) for s in frames]
        frames[0].save(os.path.join(OUT, "step%02d.gif" % k), save_all=True, append_images=frames[1:], duration=90, loop=0, optimize=True)
    r.close()
    return {"step": k, "title": title, "parts": [[n_, q] for n_, c, q in legend]}

if __name__ == "__main__":
    man = []
    for k, s in enumerate(STEPS, 1):
        if ONLY and k not in ONLY: continue
        man.append(render(k, *s)); print("step", k, s[0], flush=True)
    if not ONLY: json.dump(man, open(os.path.join(OUT, "steps.json"), "w"), indent=1)
