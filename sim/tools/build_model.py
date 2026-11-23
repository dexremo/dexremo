"""Build URDF + MJCF for the DexRemo hand from the STEP-derived parts (read_step.py) and links (links.py).
Usage: python3 build_model.py <parts dir> <output package dir> [model name] [scene file name]
The model name (default dexremo_hand) names the MJCF/URDF files and the mesh folder meshes/<model name>/.
All lengths in metres. The base frame sits at the centre of the Franka flange's mounting face, axes as in the CAD;
fingers point along +z."""
import json, math, os, sys
import numpy as np, trimesh

SRC, OUT = sys.argv[1], sys.argv[2]
MODEL = sys.argv[3] if len(sys.argv) > 3 else "dexremo_hand"
SCENE = sys.argv[4] if len(sys.argv) > 4 else "scene.xml"
P = json.load(open(os.path.join(SRC, "parts.json"))); L = json.load(open(os.path.join(SRC, "links.json")))
G = {int(k): v for k, v in L["groups"].items()}; J = {j["servo"]: j for j in L["joints"]}
MESH = {p["idx"]: trimesh.load(os.path.join(SRC, "parts", p["file"])) for p in P}

# ---------------- assumptions to confirm with the hardware team ----------------
SERVO_MASS = 0.055                                   # kg, STS3215 (datasheet value, to confirm)
DENSITY = {"pla": 1240.0, "steel": 7850.0}          # kg/m^3; printed parts taken as solid PLA (a rough upper bound)
MATERIAL = {"tension-sensor": "steel"}               # bought load cells; every other non-servo part is printed PLA
EFFORT, VELOCITY = 1.9, 4.7                          # N m, rad/s (STS3215 at 7.4 V, to confirm)
LIMIT = math.radians(90)                             # placeholder range +-90 deg until measured limits arrive
# --------------------------------------------------------------------------------

# base frame: centre of the Franka flange's mounting face; a hand without the flange (the leader device) uses the centre of
# the palm's back face, where the connector would sit
fl = next((p for p in P if p["part"] == "franka_flange"), None) or [p for p in P if p["part"] == "hand-base"][0]
ORIGIN = np.array([(fl["bbox_min_mm"][0] + fl["bbox_max_mm"][0]) / 2, (fl["bbox_min_mm"][1] + fl["bbox_max_mm"][1]) / 2, fl["bbox_min_mm"][2]]) / 1000
ATTACH = "franka_attach" if fl["part"] == "franka_flange" else "mount_site"

palm = [g for g, m in G.items() if any(P[i]["part"] == "hand-base" for i in m)][0]
FINGERS = {}
for f, base_servo_y in (("left", 0.0755), ("mid", 0.0255), ("right", -0.0245)):
    # joint 1 of each finger: the servo in the palm group whose shaft point is at this finger's y
    s1 = min((s for s in J if J[s]["parent"] == palm), key=lambda s: abs(J[s]["point"][1] - base_servo_y))
    chain, cur, seen = [], palm, {palm}
    s = s1
    while s is not None:
        j = J[s]; a, b = j["parent"], j["children"][0]
        child = b if a == cur else a                 # the servo body may sit on either side of the joint
        flip = a != cur                              # body on the child side: the horn drives the parent
        chain.append({"servo": s, "parent": cur, "child": child, "flip": flip}); seen.add(child); cur = child
        s = next((t for t in J if t not in [c["servo"] for c in chain] and cur in (J[t]["parent"], *J[t]["children"])
                  and ({J[t]["parent"], *J[t]["children"]} - seen)), None)
    assert len(chain) == 4, (f, chain)
    FINGERS[f] = chain
JNAMES = ["cmc1", "cmc2", "mcp", "ip"]

def part_mass(i):
    p = P[i]
    if p["part"] == "STS3215_03a.step": return SERVO_MASS
    return DENSITY[MATERIAL.get(p["part"], "pla")] * p["volume_cm3"] * 1e-6

def inertial(idxs, frame):
    """Mass, centre of mass and inertia about the CoM of a group of parts, in a frame whose origin is `frame` (axes = base)."""
    m_tot, com, I = 0.0, np.zeros(3), np.zeros((3, 3)); items = []
    for i in idxs:
        mesh = MESH[i]; m = part_mass(i)
        if mesh.is_volume:
            mp = mesh.mass_properties; vol = max(mp["volume"], 1e-12)
            c = mp["center_mass"]; Ic = mp["inertia"] / mp["density"] / vol * m      # scale unit-density inertia to this mass
        else:                                                            # fall back to a solid box over the part's extent
            lo, hi = mesh.bounds; c = (lo + hi) / 2; e = hi - lo
            Ic = m / 12 * np.diag([e[1]**2 + e[2]**2, e[0]**2 + e[2]**2, e[0]**2 + e[1]**2])
        items.append((m, c, Ic)); m_tot += m; com += m * c
    com /= m_tot
    for m, c, Ic in items:
        d = c - com; I += Ic + m * (np.dot(d, d) * np.eye(3) - np.outer(d, d))
    return m_tot, com - frame, I

def ensure(d): os.makedirs(d, exist_ok=True); return d
VIS, COL = ensure(os.path.join(OUT, "meshes", MODEL, "visual")), ensure(os.path.join(OUT, "meshes", MODEL, "collision"))
ensure(os.path.join(OUT, "urdf")); ensure(os.path.join(OUT, "mjcf"))

LINKS = []                                           # (name, parent name, joint dict or None, part idxs, frame origin)
LINKS.append(("base_link", None, None, G[palm], ORIGIN))
SENSORS = []; TIPS = []
for f, chain in FINGERS.items():
    parent_name, parent_origin = "base_link", ORIGIN
    for k, c in enumerate(chain):
        j = J[c["servo"]]; pt = np.array(j["point"]); ax = np.array(j["dir"]) * (-1 if c["flip"] else 1)
        name = "%s_%s_link" % (f, JNAMES[k]); members = list(G[c["child"]])
        if k == 3:
            # fingertip point: the far end of the distal group along the finger (+z in the CAD pose, fingers parallel)
            V = np.vstack([MESH[i].vertices for i in members if P[i]["part"] != "STS3215_03a.step"])
            tip_pt = V[V[:, 2] > V[:, 2].max() - 0.001].mean(axis=0)
        if k == 3 and any(P[i]["part"] == "force_sensor_layer1" for i in members):   # split the distal group at the force sensor: tip body = nail + outer plate
            layers = sorted([i for i in members if P[i]["part"] == "force_sensor_layer1"], key=lambda i: np.array(P[i]["T"])[2][3])
            cells = [i for i in members if P[i]["part"] == "tension-sensor"]
            inner, outer = [(np.array(P[i]["bbox_min_mm"]) + np.array(P[i]["bbox_max_mm"])) / 2000 for i in layers]
            n = (outer - inner) / np.linalg.norm(outer - inner); site = (inner + outer) / 2
            tip = [i for i in members if np.dot((np.array(P[i]["bbox_min_mm"]) + np.array(P[i]["bbox_max_mm"])) / 2000 - site, n) > 0]
            LINKS.append((name, parent_name, {"name": "%s_%s" % (f, JNAMES[k]), "point": pt, "axis": ax}, [i for i in members if i not in tip], pt))
            LINKS.append(("%s_tip" % f, name, {"name": "%s_tip_fixed" % f, "point": site, "axis": None}, tip, site))
            # sensor +X: towards the single load cell (the one not split across the IP axis); Y = Z x X is then parallel to the IP axis
            cc = [(np.array(P[i]["bbox_min_mm"]) + np.array(P[i]["bbox_max_mm"])) / 2000 for i in cells]
            ip_ = [v - site - np.dot(v - site, n) * n for v in cc]
            single = min(ip_, key=lambda v: abs(np.dot(v / np.linalg.norm(v), ax)))
            xd = np.cross(ax, n); xd = xd / np.linalg.norm(xd) * np.sign(np.dot(xd, single))   # exactly normal to the IP axis
            SENSORS.append({"finger": f, "body": "%s_tip" % f, "pos": site, "normal": n, "xdir": xd})
            TIPS.append({"finger": f, "body": "%s_tip" % f, "pos": tip_pt})
        else:
            LINKS.append((name, parent_name, {"name": "%s_%s" % (f, JNAMES[k]), "point": pt, "axis": ax}, members, pt))
            if k == 3: TIPS.append({"finger": f, "body": name, "pos": tip_pt})
        parent_name, parent_origin = name, pt

# ---------------- zero pose ----------------
# The CAD assembly has the fingers parallel. The real hand (and the leader device) is calibrated with the side fingers turned
# outwards and each finger bent into a hook; fit_zero.py recovers these angles exactly from the leader CAD. Re-pose every link
# by them so that q = 0 in the model is the real hand's zero.
ZERO = {"left_cmc1": -90, "mid_cmc1": 0, "right_cmc1": 90, "cmc2": 0, "mcp": 45, "ip": -90}      # degrees, in the CAD joint convention
def rot(point, axis, q):
    T = np.eye(4); R = trimesh.transformations.rotation_matrix(q, axis)[:3, :3]
    T[:3, :3] = R; T[:3, 3] = point - R @ point; return T
pose = {"base_link": np.eye(4)}; posed = []
for name, parent, joint, idxs, frame in LINKS:
    if parent is None: posed.append((name, parent, joint, idxs, frame)); continue
    Tp = pose[parent]
    if joint["axis"] is None: T = Tp
    else:
        f_, jt = joint["name"].split("_", 1)
        q = math.radians(ZERO.get(joint["name"], ZERO.get(jt, 0)))
        T = Tp @ rot(joint["point"], joint["axis"], q)
        joint["point"] = (T @ np.r_[joint["point"], 1])[:3]; joint["axis"] = T[:3, :3] @ joint["axis"]
    pose[name] = T
    for i in idxs: MESH[i].apply_transform(T)
    for s in SENSORS:
        if s["body"] == name: s["pos"] = (T @ np.r_[s["pos"], 1])[:3]; s["normal"] = T[:3, :3] @ s["normal"]; s["xdir"] = T[:3, :3] @ s["xdir"]
    for s in TIPS:
        if s["body"] == name: s["pos"] = (T @ np.r_[s["pos"], 1])[:3]
    posed.append((name, parent, joint, idxs, (T @ np.r_[frame, 1])[:3]))
LINKS = posed
if os.environ.get("DUMP_POSED"):                     # optional: every part, posed at q = 0, for display models (e.g. the website GLB)
    d_ = ensure(os.environ["DUMP_POSED"])
    for i, m_ in MESH.items(): m_.export(os.path.join(d_, "%03d_%s.stl" % (i, P[i]["part"].split(" gb_")[0][:40].replace(" ", "_"))))

def xyz(v): return " ".join("%.6f" % x for x in v)
def frame_quat(x, z):
    """Quaternion (w x y z) of the frame with axes x, z x x, z."""
    z = z / np.linalg.norm(z); x = x - np.dot(x, z) * z; x /= np.linalg.norm(x)
    q = trimesh.transformations.quaternion_from_matrix(np.r_[np.c_[np.c_[x, np.cross(z, x), z], np.zeros(3)], [[0, 0, 0, 1]]])
    return q if q[0] >= 0 else -q
def zaxis_quat(n):
    """Quaternion (w x y z) rotating +z onto n."""
    z = np.array([0, 0, 1.0]); v = np.cross(z, n); s = np.linalg.norm(v); c = np.dot(z, n)
    if s < 1e-9: return np.array([1, 0, 0, 0.0]) if c > 0 else np.array([0, 1, 0, 0.0])
    ang = math.atan2(s, c); v /= s; return np.r_[math.cos(ang / 2), v * math.sin(ang / 2)]

origin_of = {}; total = 0.0
for name, parent, joint, idxs, frame in LINKS:
    origin_of[name] = frame
    vis = trimesh.util.concatenate([MESH[i] for i in idxs]); vis.apply_translation(-frame); vis.export(os.path.join(VIS, name + ".stl"))
    for k, i in enumerate(idxs):
        h = MESH[i].convex_hull.copy(); h.apply_translation(-frame); h.export(os.path.join(COL, "%s_%d.stl" % (name, k)))
    total += sum(part_mass(i) for i in idxs)

# ---------------- URDF ----------------
U = ['<?xml version="1.0"?>', '<!-- DexRemo three-finger hand. Generated from the STEP assembly; see README for assumptions. -->', '<robot name="%s">' % MODEL]
for name, parent, joint, idxs, frame in LINKS:
    m, com, I = inertial(idxs, frame)
    U.append('  <link name="%s">' % name)
    U.append('    <inertial><origin xyz="%s"/><mass value="%.5f"/><inertia ixx="%.3e" ixy="%.3e" ixz="%.3e" iyy="%.3e" iyz="%.3e" izz="%.3e"/></inertial>'
             % (xyz(com), m, I[0, 0], I[0, 1], I[0, 2], I[1, 1], I[1, 2], I[2, 2]))
    U.append('    <visual><geometry><mesh filename="../meshes/%s/visual/%s.stl"/></geometry></visual>' % (MODEL, name))
    for k in range(len(idxs)):
        U.append('    <collision><geometry><mesh filename="../meshes/%s/collision/%s_%d.stl"/></geometry></collision>' % (MODEL, name, k))
    U.append('  </link>')
    if parent:
        po = origin_of[parent]
        if joint["axis"] is None:
            U.append('  <joint name="%s" type="fixed"><parent link="%s"/><child link="%s"/><origin xyz="%s"/></joint>' % (joint["name"], parent, name, xyz(frame - po)))
        else:
            U.append('  <joint name="%s" type="revolute"><parent link="%s"/><child link="%s"/><origin xyz="%s"/><axis xyz="%s"/>'
                     '<limit lower="%.4f" upper="%.4f" effort="%.2f" velocity="%.2f"/><dynamics damping="0.1"/></joint>'
                     % (joint["name"], parent, name, xyz(frame - po), xyz(joint["axis"]), -LIMIT, LIMIT, EFFORT, VELOCITY))
U.append('</robot>')
open(os.path.join(OUT, "urdf", MODEL + ".urdf"), "w").write("\n".join(U) + "\n")

# ---------------- MJCF ----------------
children = {}
for L_ in LINKS: children.setdefault(L_[1], []).append(L_)
def body(L_, depth):
    name, parent, joint, idxs, frame = L_; pad = "  " * depth
    po = origin_of[parent] if parent else frame          # the root body sits at the world origin: base frame = flange face
    m, com, I = inertial(idxs, frame)
    out = ['%s<body name="%s" pos="%s">' % (pad, name, xyz(frame - po))]
    out.append('%s  <inertial pos="%s" mass="%.5f" fullinertia="%.3e %.3e %.3e %.3e %.3e %.3e"/>' % (pad, xyz(com), m, I[0, 0], I[1, 1], I[2, 2], I[0, 1], I[0, 2], I[1, 2]))
    if joint and joint["axis"] is not None:
        out.append('%s  <joint name="%s" axis="%s" range="%.4f %.4f"/>' % (pad, joint["name"], xyz(joint["axis"]), -LIMIT, LIMIT))
    out.append('%s  <geom class="visual" mesh="%s"/>' % (pad, name))
    for k in range(len(idxs)): out.append('%s  <geom class="collision" mesh="%s_%d"/>' % (pad, name, k))
    if name == "base_link": out.append('%s  <site name="%s" pos="0 0 0" size="0.005" rgba="1 0.5 0 1"/>' % (pad, ATTACH))
    for s in SENSORS:
        if s["body"] == name: out.append('%s  <site name="%s_force_site" pos="0 0 0" quat="%s" size="0.004" rgba="0.2 0.8 1 1"/>' % (pad, s["finger"], xyz(frame_quat(s["xdir"], s["normal"]))))
    for s in TIPS:
        if s["body"] == name: out.append('%s  <site name="%s_tip_site" pos="%s" size="0.003" rgba="1 0.2 0.2 1"/>' % (pad, s["finger"], xyz(s["pos"] - frame)))
    for ch in children.get(name, []): out += body(ch, depth + 1)
    out.append("%s</body>" % pad); return out

meshes = ['    <mesh name="%s" file="visual/%s.stl"/>' % (L_[0], L_[0]) for L_ in LINKS]
for name, parent, joint, idxs, frame in LINKS:
    meshes += ['    <mesh name="%s_%d" file="collision/%s_%d.stl"/>' % (name, k, name, k) for k in range(len(idxs))]
joints = [L_[2]["name"] for L_ in LINKS if L_[2] and L_[2]["axis"] is not None]
X = ['<mujoco model="%s">' % MODEL, '  <!-- DexRemo three-finger hand. Generated from the STEP assembly; see README for assumptions. -->',
     '  <compiler angle="radian" meshdir="../meshes/%s" autolimits="true"/>' % MODEL, '  <option integrator="implicitfast"/>',
     '  <default>', '    <joint damping="0.1" armature="0.005" frictionloss="0.01"/>',
     '    <position kp="6" forcerange="-%.2f %.2f"/>' % (EFFORT, EFFORT),
     '    <default class="visual"><geom type="mesh" contype="0" conaffinity="0" group="2" rgba="0.18 0.19 0.21 1"/></default>',
     '    <default class="collision"><geom type="mesh" group="3" rgba="0.9 0.4 0.1 0.35" friction="0.8 0.02 0.001"/></default>',
     '  </default>', '  <asset>'] + meshes + ['  </asset>', '  <worldbody>'] + body(LINKS[0], 2) + ['  </worldbody>']
X += ['  <actuator>'] + ['    <position name="%s_act" joint="%s" ctrlrange="%.4f %.4f"/>' % (j, j, -LIMIT, LIMIT) for j in joints] + ['  </actuator>']
X += ['  <sensor>'] + ['    <force name="%s_force" site="%s_force_site"/>' % (s["finger"], s["finger"]) for s in SENSORS] \
     + ['    <framepos name="%s_tip_pos" objtype="site" objname="%s_tip_site" reftype="body" refname="base_link"/>' % (s["finger"], s["finger"]) for s in TIPS] \
     + ['    <jointpos name="%s_pos" joint="%s"/>' % (j, j) for j in joints] + ['  </sensor>', '  <!--CONTACT_EXCLUDES-->', '</mujoco>']
hand_xml = "\n".join(X) + "\n"
# bodies whose meshes already overlap at the zero pose (each finger's first link sits inside the palm pocket) never collide
import mujoco
m0 = mujoco.MjModel.from_xml_string(hand_xml.replace("../meshes", os.path.abspath(os.path.join(OUT, "meshes"))))
d0 = mujoco.MjData(m0); mujoco.mj_forward(m0, d0)
pairs = sorted({tuple(sorted((mujoco.mj_id2name(m0, mujoco.mjtObj.mjOBJ_BODY, m0.geom_bodyid[c.geom1]),
                              mujoco.mj_id2name(m0, mujoco.mjtObj.mjOBJ_BODY, m0.geom_bodyid[c.geom2])))) for c in d0.contact[:d0.ncon]})
excl = "  <contact>\n" + "".join('    <exclude body1="%s" body2="%s"/>\n' % p for p in pairs) + "  </contact>"
hand_xml = hand_xml.replace("  <!--CONTACT_EXCLUDES-->", excl)
open(os.path.join(OUT, "mjcf", MODEL + ".xml"), "w").write(hand_xml)
# demo scene: the hand hangs fingers-down from a fixed mount 0.45 m above a floor, as on the arm
lines = hand_xml.split("\n"); a = lines.index("  <worldbody>"); b = lines.index("  </worldbody>")
scene = lines[:a] + [
    '  <visual><headlight diffuse="0.6 0.6 0.6" ambient="0.35 0.35 0.35"/><global offwidth="1600" offheight="1200"/></visual>',
    '  <asset><texture name="sky" type="skybox" builtin="gradient" rgb1="0.93 0.93 0.95" rgb2="0.75 0.78 0.83" width="256" height="256"/>',
    '    <texture name="grid" type="2d" builtin="checker" rgb1="0.92 0.92 0.9" rgb2="0.85 0.85 0.83" width="512" height="512"/>',
    '    <material name="grid" texture="grid" texrepeat="8 8"/></asset>',
    '  <worldbody>', '    <light pos="0.3 -0.4 1.2" dir="-0.3 0.4 -1" diffuse="0.7 0.7 0.7"/>',
    '    <geom name="floor" type="plane" size="1 1 0.01" material="grid"/>',
    '    <body name="mount" pos="0 0 0.45" quat="0 1 0 0">'] + ["  " + s for s in lines[a + 1:b]] + ['    </body>'] + lines[b:]
scene[0] = '<mujoco model="%s_scene">' % MODEL
open(os.path.join(OUT, "mjcf", SCENE), "w").write("\n".join(scene))
json.dump({"part_link": {str(i): L_[0] for L_ in LINKS for i in L_[3]}, "origin": ORIGIN.tolist(), "joints": joints, "sensors": [s["finger"] for s in SENSORS], "total_mass_kg": round(total, 3)}, open(os.path.join(OUT, "build_info_%s.json" % MODEL), "w"), indent=1)
print("links", len(LINKS), "| joints", len(joints), "| estimated mass %.3f kg" % total)
for f, ch in FINGERS.items(): print(f, [("flip" if c["flip"] else "") + str(c["servo"]) for c in ch])
