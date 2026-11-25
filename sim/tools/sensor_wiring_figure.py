"""Schematic figures for the fingertip force sensor: wiring and labelling.

Usage: python sensor_wiring_figure.py <out_dir>   (e.g. hardware/img)
Writes sensor_wiring.png, sensor_wiring_zh.png, sensor_labels.png, sensor_labels_zh.png.
"""
import sys, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, Rectangle, FancyArrowPatch, Wedge

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
from matplotlib import font_manager
font_manager.fontManager.addfont("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
CJK = "Noto Sans CJK JP"

RED, BLACK, GREEN, WHITE = "#d62728", "#222222", "#2ca02c", "#bbbbbb"
TERM = "#7fc97f"; TERM_E = "#5aa75a"
INK, INK2, MUTED = "#1f2328", "#57606a", "#8c959f"
TAG = "#ffd43b"

T = {
 "en": dict(
   cell="Load cell", tip="Fingertip 1",
   inputs="Transmitter: load-cell inputs (one 4-pin block per channel)",
   more="Channels 4#–9#:\nfingertips 2 and 3,\nwired the same way",
   outputs="Transmitter: power and RS485",
   psu="24 V DC\npower supply", adapter="RS485–USB adapter", pc="Computer\n(USB)",
   unused="not used",
   legend=[(RED, "red  → E+"), (BLACK, "black → E−"), (WHITE, "white → S−"), (GREEN, "green → S+")],
   rs="A → T/R+,  B → T/R−", pw="V+ → 24 V +,  GND → 24 V −",
   title_a="(a) Load cells to the transmitter", title_b="(b) Transmitter to power and computer",
   tagnote="cable tag",
 ),
 "zh": dict(
   cell="拉压力传感器", tip="1 号指尖",
   inputs="变送器：荷重信号输入（每个通道一组 4 个端子）",
   more="4#–9# 通道：\n2 号、3 号指尖，\n接法相同",
   outputs="变送器：供电和 RS485",
   psu="24 V 直流\n电源", adapter="RS485 转 USB", pc="电脑\n（USB）",
   unused="不接",
   legend=[(RED, "红 → E+"), (BLACK, "黑 → E−"), (WHITE, "白 → S−"), (GREEN, "绿 → S+")],
   rs="A → T/R+，B → T/R−", pw="V+ → 24 V 正极，GND → 24 V 负极",
   title_a="(a) 传感器接到变送器", title_b="(b) 变送器接电源和电脑",
   tagnote="线标",
 ),
}


def box(ax, x, y, w, h, fc, ec=INK, r=0.08, lw=1.4, z=2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, zorder=z))


def terminal_strip(ax, x0, y, labels, pitch, fc_map=None, greyed=()):
    """Draw a row of screw terminals; return dict label -> (x, y_bottom)."""
    pos = {}
    w = pitch * len(labels)
    box(ax, x0 - 0.1, y - 0.42, w + 0.2, 0.84, "#e9ecef", r=0.06)
    for i, lab in enumerate(labels):
        cx = x0 + pitch * (i + 0.5)
        g = lab in greyed
        fc = "#dee2e6" if g else (fc_map(lab) if fc_map else TERM)
        ax.add_patch(Rectangle((cx - pitch * 0.42, y - 0.36), pitch * 0.84, 0.72, fc=fc, ec=INK, lw=1, zorder=3))
        ax.add_patch(Circle((cx, y + 0.08), 0.15, fc="#f1f3f5", ec=INK, lw=0.9, zorder=4))
        ax.plot([cx - 0.1, cx + 0.1], [y + 0.08, y + 0.08], color=INK, lw=0.9, zorder=5)
        ax.text(cx, y - 0.22, lab, ha="center", va="center", fontsize=8.5, zorder=5,
                color=MUTED if g else INK, fontweight="bold")
        pos[lab] = (cx, y - 0.42)
    return pos


def wire(ax, pts, color, lw=2.4):
    xs, ys = zip(*pts)
    if color == WHITE:
        ax.plot(xs, ys, color="#6e7781", lw=lw + 1.4, solid_capstyle="round", zorder=6)
    ax.plot(xs, ys, color=color, lw=lw, solid_capstyle="round", zorder=7)


def wiring(lang):
    t = T[lang]
    plt.rcParams["font.family"] = [CJK, "DejaVu Sans"] if lang == "zh" else ["DejaVu Sans"]
    fig, axs = plt.subplots(2, 1, figsize=(11, 9.6), gridspec_kw=dict(height_ratios=[1.1, 1]))
    # ---------- (a) load cells -> per-channel input blocks ----------
    ax = axs[0]
    ax.set_xlim(0, 11); ax.set_ylim(0, 5.6); ax.axis("off"); ax.set_aspect("equal")
    ax.text(0.1, 5.45, t["title_a"], fontsize=13, fontweight="bold", va="top", color=INK)
    order = ["E+", "E−", "S−", "S+"]
    cols = {"E+": RED, "E−": BLACK, "S−": WHITE, "S+": GREEN}
    pitch = 0.55
    cells = [("1+X", "1#"), ("1+Y", "2#"), ("1−Y", "3#")]
    xs = [1.9, 4.55, 7.2]
    ax.text(5.35, 4.95, t["inputs"], ha="center", fontsize=10.5, color=INK2)
    box(ax, 0.7, 0.15, 8.85, 1.55, "#f6f8fa", ec=MUTED, r=0.2, lw=1.2, z=1)
    ax.text(0.85, 0.95, t["tip"], fontsize=10.5, color=INK2, va="center", fontweight="bold")
    for (name, ch), x0 in zip(cells, xs):
        pos = terminal_strip(ax, x0, 4.1, order, pitch,
                             fc_map=lambda l: TERM_E if l.startswith("E") else TERM)
        ax.text(x0 + pitch * 2, 4.62, ch, ha="center", fontsize=11, fontweight="bold", color=INK)
        cx = x0 + pitch * 2
        ax.add_patch(Rectangle((cx - 0.6, 0.45), 1.2, 0.8, fc="#ced4da", ec=INK, lw=1.2, zorder=3))
        ax.add_patch(Rectangle((cx - 0.32, 0.6), 0.64, 0.5, fc="#495057", ec=INK, lw=0.8, zorder=4))
        ax.text(cx, 0.3, f"{t['cell']} {name}", ha="center", fontsize=9, color=INK)
        for j, lab in enumerate(order):
            sx = cx + (j - 1.5) * 0.18
            tx = pos[lab][0]
            wire(ax, [(sx, 1.25), (sx, 2.6), (tx, 3.2), pos[lab]], cols[lab])
        ax.add_patch(FancyBboxPatch((cx - 0.45, 1.85), 0.9, 0.36, boxstyle="round,pad=0,rounding_size=0.05",
                                    fc=TAG, ec="#b08900", lw=1, zorder=9))
        ax.text(cx, 2.03, name, ha="center", va="center", fontsize=9.5, fontweight="bold", zorder=10)
    ax.text(9.75, 4.1, t["more"], fontsize=9.5, color=INK2, va="center", linespacing=1.4)
    ax.annotate(t["tagnote"], xy=(xs[0] + pitch * 2 - 0.45, 2.03), xytext=(0.9, 2.03), fontsize=9.5, color=INK2,
                arrowprops=dict(arrowstyle="->", color=INK2, lw=1), ha="center", va="center")
    for i, (c, lab) in enumerate(t["legend"]):
        yy = 3.95 - i * 0.34
        if c == WHITE:
            ax.plot([0.1, 0.5], [yy, yy], color="#6e7781", lw=3.8)
        ax.plot([0.1, 0.5], [yy, yy], color=c, lw=2.4)
        ax.text(0.6, yy, lab, va="center", fontsize=9.5, color=INK)

    # ---------- (b) V+/GND/A/B -> PSU + adapter ----------
    ax = axs[1]
    ax.set_xlim(0, 11); ax.set_ylim(0, 5.0); ax.axis("off"); ax.set_aspect("equal")
    ax.text(0.1, 4.85, t["title_b"], fontsize=13, fontweight="bold", va="top", color=INK)
    p2 = 0.9; ox = 3.6
    po = terminal_strip(ax, ox, 3.7, ["V+", "GND", "A", "B"], p2)
    ax.text(ox + p2 * 2, 4.28, t["outputs"], ha="center", fontsize=10.5, color=INK2)
    box(ax, 0.3, 0.5, 2.3, 1.5, "#f1f3f5")
    ax.text(1.45, 1.05, t["psu"], ha="center", va="center", fontsize=10, color=INK, linespacing=1.3)
    for lab, xx, c in [("+", 1.0, RED), ("−", 1.9, BLACK)]:
        ax.add_patch(Circle((xx, 1.72), 0.14, fc=c, ec=INK, zorder=8))
        ax.text(xx, 1.72, lab, ha="center", va="center", color="white", fontsize=10, fontweight="bold", zorder=9)
    wire(ax, [(1.0, 1.86), (1.0, 2.6), (po["V+"][0], 2.6), po["V+"]], RED)
    wire(ax, [(1.9, 1.86), (1.9, 2.3), (po["GND"][0], 2.3), po["GND"]], BLACK)
    ax.text(0.3, 2.95, t["pw"], fontsize=10, fontweight="bold", color=INK)
    ax_x = 4.9
    pa = terminal_strip(ax, ax_x, 1.15, ["T/R+", "T/R−", "RXD+", "RXD−", "GND"], 0.78,
                        greyed=("RXD+", "RXD−", "GND"))
    box(ax, ax_x + 0.78 * 5 + 0.15, 0.7, 1.0, 0.9, "#4263eb", ec=INK, r=0.12)
    ax.text(ax_x + 0.78 * 5 + 0.65, 1.15, "USB", ha="center", va="center", color="white", fontsize=9, fontweight="bold")
    ax.text(ax_x + 0.78 * 2.5, 0.35, t["adapter"], ha="center", fontsize=10.5, color=INK2)
    ax.text(ax_x + 0.78 * 3.5, 1.72, t["unused"], ha="center", fontsize=9, color=MUTED, style="italic")
    top = lambda p: (p[0], p[1] + 0.84)
    wire(ax, [po["A"], (po["A"][0], 2.6), (pa["T/R+"][0], 2.6), top(pa["T/R+"])], "#f08c00")
    wire(ax, [po["B"], (po["B"][0], 2.3), (pa["T/R−"][0], 2.3), top(pa["T/R−"])], "#e8590c")
    ax.text(7.6, 2.95, t["rs"], fontsize=10, fontweight="bold", color=INK)
    ux = ax_x + 0.78 * 5 + 1.15
    ax.plot([ux, 10.0], [1.15, 1.15], color="#adb5bd", lw=4, solid_capstyle="round", zorder=1)
    box(ax, 10.0, 0.7, 0.95, 0.9, "#f1f3f5", r=0.1)
    ax.text(10.47, 1.15, t["pc"], ha="center", va="center", fontsize=8.5, color=INK, linespacing=1.2)
    fig.tight_layout()
    name = "sensor_wiring" + ("_zh" if lang == "zh" else "") + ".png"
    fig.savefig(os.path.join(OUT, name), dpi=160, facecolor="white")
    plt.close(fig)


MARK = "#c92a2a"   # marker-pen red

L = {
 "en": dict(
   title_a="(a) Top face of the sensor (outer plate), seen from outside",
   title_b="(b) Side view: mark every load cell",
   title_c="(c) Cable tags",
   top="TOP", num="3", numnote="fingertip number",
   topnote="\"TOP\": this face points\nout of the fingertip (+Z)",
   xnote="+X arrow: towards the\nsingle load cell", ynote="+Y arrow: 90° anticlockwise\nfrom +X (right-hand rule)",
   cellnote="write the position on\neach load cell body",
   outer="outer plate (top)", inner="inner plate",
   tagtext="Tag each cable with the full name:\nfingertip number + position.",
   numside="number on the\ninner plate too",
 ),
 "zh": dict(
   title_a="(a) 传感器顶面（外板），从指尖外面看",
   title_b="(b) 侧面：每个拉压力传感器都要标",
   title_c="(c) 线标",
   top="顶", num="3", numnote="指尖编号",
   topnote="写\"顶\"：这一面朝向\n指尖外侧（+Z）",
   xnote="+X 箭头：指向单独\n那个拉压力传感器", ynote="+Y 箭头：从 +X 逆时针转 90°\n（右手定则）",
   cellnote="在每个拉压力传感器\n本体上写它的位置",
   outer="外板（顶面）", inner="内板",
   tagtext="每根线都贴线标，写全名：\n指尖编号 + 位置。",
   numside="内板侧面也\n写上编号",
 ),
}


def hand(ax, x, y, s, size=15, rot=0, **kw):
    ax.text(x, y, s, color=MARK, fontsize=size, fontweight="bold", rotation=rot,
            ha="center", va="center", zorder=12, **kw)


def marker_arrow(ax, p0, p1, lw=3):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>,head_length=0.35,head_width=0.22",
                                 color=MARK, lw=lw, zorder=11, mutation_scale=20))


def labels(lang):
    t = L[lang]
    plt.rcParams["font.family"] = [CJK, "DejaVu Sans"] if lang == "zh" else ["DejaVu Sans"]
    fig = plt.figure(figsize=(13.5, 6.6))
    # ---------- (a) top view ----------
    ax = fig.add_axes([0.0, 0.0, 0.46, 0.93])
    ax.set_xlim(-3.3, 3.3); ax.set_ylim(-3.2, 3.2); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(t["title_a"], fontsize=12.5, fontweight="bold", color=INK, loc="left")
    R = 2.0
    ax.add_patch(Circle((0, 0), R, fc="#f8f9fa", ec=INK, lw=1.6, zorder=2))
    ax.add_patch(Circle((0, 0), 0.55, fc="white", ec=INK, lw=1.3, zorder=3))
    names = {0: "+X", 120: "+Y", 240: "−Y"}
    for ang in (0, 120, 240):
        a = np.radians(ang); r = 1.35
        ax.add_patch(Circle((r * np.cos(a), r * np.sin(a)), 0.2, fc="#ced4da", ec=INK, lw=1.1, zorder=4))
        ax.add_patch(Circle((r * np.cos(a), r * np.sin(a)), 0.08, fc="#868e96", ec=INK, lw=0.6, zorder=5))
        b = np.radians(ang + 60)
        ax.add_patch(Circle((r * np.cos(b), r * np.sin(b)), 0.12, fc="white", ec=INK, lw=1, zorder=4))
        # dashed outline of the load cell underneath
        c = np.array([r * np.cos(a), r * np.sin(a)])
        d = np.array([np.cos(a), np.sin(a)]); e = np.array([-d[1], d[0]])
        corners = [c + 0.32 * d + 0.25 * e, c - 0.32 * d + 0.25 * e, c - 0.32 * d - 0.25 * e, c + 0.32 * d - 0.25 * e, c + 0.32 * d + 0.25 * e]
        ax.plot(*zip(*corners), ls="--", color=MUTED, lw=0.9, zorder=3)
    # marker marks
    marker_arrow(ax, (0.62, 0), (1.05, 0))
    hand(ax, 0.95, 0.32, "+X", 14)
    marker_arrow(ax, (0, 0.62), (0, 1.25))
    hand(ax, 0.32, 1.1, "+Y", 14)
    hand(ax, -0.9, -0.35, t["top"], 16)
    hand(ax, 1.05, -0.62, t["num"], 18)
    # notes
    kw = dict(fontsize=9.5, color=INK2, arrowprops=dict(arrowstyle="->", color=INK2, lw=0.9), va="center")
    ax.annotate(t["xnote"], xy=(1.05, 0.05), xytext=(2.15, 1.35), ha="left", **kw)
    ax.annotate(t["ynote"], xy=(0.0, 1.25), xytext=(-3.2, 2.6), ha="left", **kw)
    ax.annotate(t["topnote"], xy=(-1.15, -0.4), xytext=(-3.2, -2.45), ha="left", **kw)
    ax.annotate(t["numnote"], xy=(1.15, -0.8), xytext=(1.9, -2.3), ha="left", **kw)
    # ---------- (b) side view ----------
    ax = fig.add_axes([0.49, 0.36, 0.5, 0.57])
    ax.set_xlim(0, 7.4); ax.set_ylim(0, 3.6); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(t["title_b"], fontsize=12.5, fontweight="bold", color=INK, loc="left")
    box(ax, 0.6, 2.35, 4.6, 0.6, "#f8f9fa", r=0.08)
    box(ax, 0.6, 0.55, 4.6, 0.6, "#f8f9fa", r=0.08)
    ax.text(5.3, 2.65, t["outer"], fontsize=9, color=INK2, va="center")
    ax.text(5.3, 0.85, t["inner"], fontsize=9, color=INK2, va="center")
    for x, nm in [(1.2, "+Y"), (3.55, "+X")]:
        ax.add_patch(Rectangle((x, 1.15), 1.0, 1.2, fc="#dee2e6", ec=INK, lw=1.2, zorder=3))
        hand(ax, x + 0.5, 1.75, nm, 15)
    hand(ax, 2.9, 2.65, t["top"], 13)
    hand(ax, 2.9, 0.85, t["num"], 15)
    kw2 = dict(fontsize=9.5, color=INK2, arrowprops=dict(arrowstyle="->", color=INK2, lw=0.9), va="center")
    ax.annotate(t["cellnote"], xy=(4.35, 1.75), xytext=(4.75, 1.7), ha="left", **kw2)
    ax.annotate(t["numside"], xy=(2.75, 0.75), xytext=(0.2, 0.15), ha="left", **kw2)

    # ---------- (c) cable tags ----------
    ax = fig.add_axes([0.49, 0.02, 0.5, 0.3])
    ax.set_xlim(0, 7.4); ax.set_ylim(0, 1.9); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(t["title_c"], fontsize=12.5, fontweight="bold", color=INK, loc="left")
    for i, nm in enumerate(["3+X", "3+Y", "3−Y"]):
        x = 0.4 + i * 1.25
        ax.plot([x + 0.45, x + 0.45], [0.1, 1.6], color="#343a40", lw=3, zorder=1)
        ax.add_patch(FancyBboxPatch((x, 0.65), 0.9, 0.42, boxstyle="round,pad=0,rounding_size=0.06",
                                    fc=TAG, ec="#b08900", lw=1, zorder=3))
        ax.text(x + 0.45, 0.86, nm, ha="center", va="center", fontsize=11, fontweight="bold", color=MARK, zorder=4)
    ax.text(4.2, 0.86, t["tagtext"], fontsize=9.5, color=INK2, va="center", linespacing=1.4)
    name = "sensor_labels" + ("_zh" if lang == "zh" else "") + ".png"
    fig.savefig(os.path.join(OUT, name), dpi=160, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    for lg in ("en", "zh"):
        wiring(lg)
        labels(lg)
