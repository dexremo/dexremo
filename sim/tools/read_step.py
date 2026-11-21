"""Read the full-hand STEP: list every part instance with its world placement, tessellate it, and save one STL per instance
(in the assembly frame, metres) plus parts.json describing them. Usage: python3 read_step.py <file.STEP> <out dir>"""
import json, os, sys
import numpy as np
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TDF import TDF_LabelSequence, TDF_Label
from OCP.TDataStd import TDataStd_Name
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE
from OCP.BRep import BRep_Tool
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Trsf
from OCP.IFSelect import IFSelect_RetDone
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp

src, out = sys.argv[1], sys.argv[2]; os.makedirs(os.path.join(out, "parts"), exist_ok=True)
doc = TDocStd_Document(TCollection_ExtendedString("doc"))
r = STEPCAFControl_Reader(); r.SetNameMode(True)
assert r.ReadFile(src) == IFSelect_RetDone; r.Transfer(doc)
st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

def name(lab):
    a = TDataStd_Name()
    return a.Get().ToExtString() if lab.FindAttribute(TDataStd_Name.GetID_s(), a) else "?"

def mat(trsf):
    m = np.eye(4)
    for i in range(3):
        for j in range(4): m[i, j] = trsf.Value(i + 1, j + 1)
    return m

parts = []
def walk(lab, T, path):
    if st.IsReference_s(lab):
        ref = TDF_Label(); st.GetReferredShape_s(lab, ref)
        loc = st.GetLocation_s(lab); T2 = T @ mat(loc.Transformation())
        walk(ref, T2, path + [name(lab)]); return
    if st.IsAssembly_s(lab):
        kids = TDF_LabelSequence(); st.GetComponents_s(lab, kids)
        for i in range(1, kids.Length() + 1): walk(kids.Value(i), T, path)
        return
    shape = st.GetShape_s(lab)
    BRepMesh_IncrementalMesh(shape, 0.08, False, 0.35, True)     # 0.08 mm chordal deviation
    V, F = [], []
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        face = TopoDS.Face_s(ex.Current()); loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is not None:
            Tf = mat(loc.Transformation()); base = len(V)
            for i in range(1, tri.NbNodes() + 1):
                p = tri.Node(i); V.append((Tf @ np.array([p.X(), p.Y(), p.Z(), 1.0]))[:3])
            rev = face.Orientation() == 1
            for i in range(1, tri.NbTriangles() + 1):
                a, b, c = tri.Triangle(i).Get()
                F.append((base + a - 1, base + c - 1, base + b - 1) if rev else (base + a - 1, base + b - 1, base + c - 1))
        ex.Next()
    V = np.array(V); V = (T @ np.c_[V, np.ones(len(V))].T).T[:, :3] / 1000.0      # mm -> m, assembly frame
    props = GProp_GProps(); BRepGProp.VolumeProperties_s(shape, props)
    k = len(parts); fn = "p%02d_%s.stl" % (k, name(lab).replace(" ", "_").replace("/", "_"))
    import trimesh
    trimesh.Trimesh(V, np.array(F), process=True).export(os.path.join(out, "parts", fn))
    parts.append({"idx": k, "part": name(lab), "instance": "/".join(path), "file": fn, "volume_cm3": round(props.Mass() / 1000.0, 2),
                  "bbox_min_mm": (V.min(0) * 1000).round(1).tolist(), "bbox_max_mm": (V.max(0) * 1000).round(1).tolist(), "T": T.round(6).tolist()})

roots = TDF_LabelSequence(); st.GetFreeShapes(roots)
for i in range(1, roots.Length() + 1): walk(roots.Value(i), np.eye(4), [name(roots.Value(i))])
json.dump(parts, open(os.path.join(out, "parts.json"), "w"), indent=1, ensure_ascii=False)
for p in parts:
    c = (np.array(p["bbox_min_mm"]) + np.array(p["bbox_max_mm"])) / 2
    print("%2d %-22s %-55s vol %7.1f cm3  centre (%6.1f %6.1f %6.1f)" % (p["idx"], p["part"], p["instance"][-55:], p["volume_cm3"], *c))
