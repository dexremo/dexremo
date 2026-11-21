"""Group the part instances into rigid links and find the 12 joints.
Each servo's output shaft (local axis through (12.5, 0, z), along z) is a joint. A part touching a servo's horn region
is driven by that servo; a part touching its body carries it. Parts touching each other are rigidly joined."""
import json, os, sys
import numpy as np, trimesh
from scipy.spatial import cKDTree
OUT = sys.argv[1] if len(sys.argv) > 1 else "step_out"
P = json.load(open(os.path.join(OUT, "parts.json")))
M = [trimesh.load(os.path.join(OUT, "parts", p["file"])) for p in P]
pts = [m.sample(30000) * 1000 if m.area > 0 else m.vertices * 1000 for m in M]           # mm
trees = [cKDTree(x) for x in pts]
SERVO = "STS3215_03a.step"; servos = [p["idx"] for p in P if p["part"] == SERVO]
TOL = 0.8                                                                                   # mm

def touching(i, j):
    d, _ = trees[j].query(pts[i], distance_upper_bound=TOL); return np.isfinite(d)
axis = {}
for s in servos:
    T = np.array(P[s]["T"]); R = T[:3, :3]; t = T[:3, 3]
    axis[s] = {"point": (R @ np.array([12.5, 0, 0]) + t) / 1000, "dir": R @ np.array([0, 0, 1.0])}
# classify contacts
horn, body, rigid = {s: [] for s in servos}, {s: [] for s in servos}, []
for i in range(len(P)):
    for j in range(len(P)):
        if i == j: continue
        if j in servos and i not in servos:
            m = touching(i, j)
            if m.sum() < 5: continue
            T = np.array(P[j]["T"]); loc = (np.linalg.inv(T) @ np.c_[pts[i][m], np.ones(m.sum())].T).T[:, :3]
            near = ((loc[:, 0] - 12.5) ** 2 + loc[:, 1] ** 2 < 11.5 ** 2) & (np.abs(loc[:, 2]) > 15.0)
            (horn if near.mean() > 0.5 else body)[j].append((i, int(m.sum()), round(float(near.mean()), 2)))
        elif i < j and i not in servos and j not in servos:
            if touching(i, j).sum() >= 1000: rigid.append((i, j))     # bolted faces touch over a large area; joint clearances only graze
# union-find
par = list(range(len(P)))
def f(x):
    while par[x] != x: par[x] = par[par[x]]; x = par[x]
    return x
def u(a, b): par[f(a)] = f(b)
for a, b in rigid: u(a, b)
for s in servos:
    for i, n, fr in body[s]: u(i, s)
groups = {}
for i in range(len(P)): groups.setdefault(f(i), []).append(i)
print("rigid groups:", len(groups))
for g, mem in groups.items():
    print("  group %2d: %s" % (g, ", ".join("%d:%s" % (k, P[k]["part"]) for k in sorted(mem))))
print("\njoints (servo -> parent group carries the body, child group is driven by the horn):")
J = []
for s in servos:
    kids = sorted({f(i) for i, n, fr in horn[s]})
    print("  servo %2d  parent group %2d  child groups %s  horn contacts %s" % (s, f(s), kids, [(i, P[i]["part"], fr) for i, n, fr in horn[s]]))
    J.append({"servo": s, "parent": f(s), "children": kids, "point": axis[s]["point"].tolist(), "dir": axis[s]["dir"].tolist()})
json.dump({"groups": {str(k): v for k, v in groups.items()}, "joints": J}, open(os.path.join(OUT, "links.json"), "w"), indent=1)
