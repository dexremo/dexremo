# DexRemo hand: hardware

The design files for the DexRemo three-finger hand: one assembly STEP and the STL files for every printed part.

```
step/dexremo_hand_full.step   full hand, with Franka flange adapter and hand-eye camera mount
stl/*.stl                     printed parts, one file per distinct part, in millimetres
```

## Assembly STEP

`dexremo_hand_full.step` is an AP214 assembly that keeps every part as a separate, named body. It opens in SolidWorks, Fusion, FreeCAD, Onshape and other CAD tools.

The part names match the STL file names below.

The model is in the CAD pose with the fingers parallel. The calibrated zero pose of the real hand is different; it is described in [`../sim/README.md`](../sim/README.md#zero-pose).

## Printed parts

All structural parts are 3D printed in PLA. Print the quantity shown for each file.

| File | Qty | Part |
|---|---|---|
| `hand-base.stl` | 1 | Palm, holds the three CMC1 servos |
| `hand_connector.stl` | 1 | Connects the palm to the flange adapter |
| `franka_flange.stl` | 1 | Adapter to the Franka Emika flange |
| `CMC1_left_joint.stl` | 1 | CMC1 bracket, left finger |
| `CMC1_mid_right_joint.stl` | 2 | CMC1 bracket, middle and right fingers |
| `CMC2_joints.stl` | 3 | CMC2 bracket |
| `MCP_joints.stl` | 3 | MCP link |
| `IP_joints.stl` | 3 | IP link |
| `fingertip_joints.stl` | 3 | Distal link, carries the fingertip sensor |
| `force_sensor_layer1.stl` | 6 | Fingertip sensor plates, two per finger |
| `left_finger_nail.stl` | 1 | Wedge fingertip, left |
| `mid_finger_nail.stl` | 1 | Wedge fingertip, middle |
| `right_finger_nail.stl` | 1 | Wedge fingertip, right |
| `hand_eye_cam_mount.stl` | 1 | Hand-eye camera arm (optional) |
| `camera_mount.stl` | 1 | Camera holder on the arm (optional) |

## Bought parts

| Part | Qty | Notes |
|---|---|---|
| Feetech ST-3215-C018 serial bus servo (12 V, 30 kg·cm) | 12 | Four per finger |
| Miniature tension/compression load cell (0–5 kg, M2.5) | 9 | Three per fingertip; only needed for force sensing |

The full list, with power supplies, cables, the load-cell transmitter, cameras and leader-device parts, is in [`BOM.md`](BOM.md).

## Licence

The hardware design files are licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) (see `LICENSE`). You may build, modify and share them for non-commercial use, with attribution and under the same licence. For commercial use, contact the corresponding author.
