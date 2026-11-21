# DexRemo

**DexRemo: A Force-Sensing Hand Platform and Task Suite for Contact-Rich Removal Manipulation**
Accepted to *IEEE Transactions on Robotics*.

[Project page](https://dexremo.github.io) · [Paper (arXiv)](https://arxiv.org/abs/2611.15981) · [Video](https://youtu.be/4ot1Yy7es_o)

![DexRemo zero pose](sim/docs/zero_pose.png)

This repository holds the open-source release of the DexRemo hand.

| Folder | Contents | Licence |
|---|---|---|
| [`hardware/`](hardware/) | Assembly STEP, printable STL files, bill of materials | CC BY-NC-SA 4.0 |
| [`sim/`](sim/) | URDF and MuJoCo (MJCF) models, with the scripts that build them from the STEP | MIT (meshes: CC BY-NC-SA 4.0) |

The assembly guide, the leader device and the control code will be released later. See the [roadmap](https://dexremo.github.io/roadmap.html).

## Quick start

To view the hand in MuJoCo:

```bash
pip install mujoco
python -m mujoco.viewer --mjcf=sim/mjcf/scene.xml
```

To build one, print the STL files listed in [`hardware/README.md`](hardware/README.md) and buy the parts in [`hardware/BOM.md`](hardware/BOM.md).

## Citation

```bibtex
@article{wang2026dexremo,
  title   = {DexRemo: A Force-Sensing Hand Platform and Task Suite for Contact-Rich Removal Manipulation},
  author  = {Wang, Liman and Zhong, Hanyang and Sun, Zhaole and Cao, Wenting and Jamil, Babar and Tyrrell, Andy and Luo, Shan and Zhu, Jihong},
  journal = {arXiv preprint arXiv:2611.15981},
  year    = {2026},
  note    = {Accepted to IEEE Transactions on Robotics}
}
```

## Licence

Each folder carries its own licence; see [`LICENSE`](LICENSE).
