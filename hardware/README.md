# DexRemo hand: hardware

**English** | [中文](README_zh.md)

The design files for the DexRemo three-finger hand: assembly STEP files, the STL files for every printed part, a bill of materials, an assembly guide and the force-sensor calibration method.

```
step/dexremo_hand_full.step                        full hand with force-sensing fingertips
step/dexremo_hand_no_sensor.step                   full hand, wedge nails without force sensors
step/dexremo_hand_no_sensor_mushroom_finger.step   full hand, mushroom fingertips without force sensors
step/assembly/*.step                               assemblies with every screw and nut, used by the assembly guide,
                                                   including the leader device's ring fingertip
stl/*.stl                                          printed parts, one file per distinct part, in millimetres
print/force_sensor_layer1.3mf                      Bambu Studio print file for the sensor plate, with the nut pause set
BOM.md                                             bill of materials
assembly/                                          step-by-step assembly guide
force_calibration.md                               calibration method for the fingertip force sensors
```

All three hands include the Franka flange adapter and the hand-eye camera mount.

## Assembly STEP

Each STEP file is an AP214 assembly that keeps every part as a separate, named body. It opens in SolidWorks, Fusion, FreeCAD, Onshape and other CAD tools.

The part names match the STL file names below.

The models are in the CAD pose with the fingers parallel. The calibrated zero pose of the real hand is different; it is described in [`../sim/README.md`](../sim/README.md#zero-pose).

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
| `force_sensor_layer1.stl` | 6 | Fingertip sensor plates, two per finger; embed three M3 nuts in each inner plate while printing. Print from [`print/force_sensor_layer1.3mf`](print/), which pauses for the nuts ([how](assembly/README.md#before-you-start)) |
| `left_finger_nail.stl` | 1 | Wedge fingertip, left |
| `mid_finger_nail.stl` | 1 | Wedge fingertip, middle |
| `right_finger_nail.stl` | 1 | Wedge fingertip, right |
| `mushroom_finger.stl` | 3 | Mushroom fingertip for a sponge or wipe (alternative to the nails and sensor) |
| `controller_finger.stl` | 3 | Ring fingertip for the leader device (in place of the nails and sensor) |
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
