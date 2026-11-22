"""Build the website's leader-device GLB from the posed parts that build_model.py dumps (DUMP_POSED=<dir>).
Usage: python3 make_leader_glb.py <posed dir> <out.glb>"""
import glob, os, sys, numpy as np, trimesh
from trimesh.visual.material import PBRMaterial
CAT = [("Finger ring", "#f76707", ("controller_finger",)), ("Joint bracket", "#12a594", ("CMC1_", "CMC2_")),
       ("Finger link", "#f5c211", ("MCP_joints", "IP_joints", "fingertip_joints")), ("Servo", "#343a40", ("STS3215",)),
       ("Palm", "#4c8eea", ("hand-base",))]
groups = {c[0]: [] for c in CAT}
for f in sorted(glob.glob(os.path.join(sys.argv[1], "*.stl"))):
    n = os.path.basename(f)[4:]
    c = next(c for c in CAT if any(n.startswith(k) for k in c[2])); groups[c[0]].append(trimesh.load(f))
sc = trimesh.Scene()
for name, hexc, _ in CAT:
    m = trimesh.util.concatenate(groups[name]); m.merge_vertices()
    m = trimesh.graph.smooth_shade(m, angle=np.radians(30))          # keep sharp edges sharp
    rgb = [(int(hexc[i:i + 2], 16) / 255) ** 2.2 for i in (1, 3, 5)]         # glTF colours are linear
    m.visual = trimesh.visual.TextureVisuals(material=PBRMaterial(name=name, baseColorFactor=rgb + [1.0], metallicFactor=0.0, roughnessFactor=0.6))
    sc.add_geometry(m, node_name=name, geom_name=name)
sc.export(sys.argv[2]); print(sys.argv[2], "%.1f MB" % (os.path.getsize(sys.argv[2]) / 1e6))
