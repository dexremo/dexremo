"""For each screw/nut in an assembly, list the non-fastener parts it touches. Usage: python3 fastener_map.py <parts dir>"""
import json, os, sys, numpy as np, trimesh
from scipy.spatial import cKDTree
D = sys.argv[1]; P = json.load(open(os.path.join(D, "parts.json")))
isf = lambda n: " gb_" in n
short = lambda n: n.split(" gb_")[-1].split("_")[-1][:22] if isf(n) else n
M = {p["idx"]: trimesh.load(os.path.join(D, "parts", p["file"])) for p in P}
S = {i: (m.sample(20000) * 1000 if m.area > 0 else m.vertices * 1000) for i, m in M.items()}
T = {i: cKDTree(x) for i, x in S.items()}
out = {}
for p in P:
    if not isf(p["part"]): continue
    i = p["idx"]; hits = []
    for q in P:
        j = q["idx"]
        if isf(q["part"]): continue
        d, _ = T[j].query(S[i], distance_upper_bound=0.6); n = int(np.isfinite(d).sum())
        if n > 20: hits.append((j, n))
    hits.sort(key=lambda x: -x[1]); out[i] = [j for j, n in hits]
    print(i, short(p["part"]), [(j, P[j]["part"][:20], n) for j, n in hits])
json.dump({str(k): v for k, v in out.items()}, open(os.path.join(D, "fasteners.json"), "w"))
