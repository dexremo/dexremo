# DexRemo 灵巧手：硬件

[English](README.md) | **中文**

DexRemo 三指灵巧手的设计文件：装配 STEP、所有打印件的 STL、物料清单、装配教程和力传感器标定方法。

```
step/dexremo_hand_full.step                        整手，带力传感指尖
step/dexremo_hand_no_sensor.step                   整手，楔形指尖，不带力传感器
step/dexremo_hand_no_sensor_mushroom_finger.step   整手，蘑菇头指尖，不带力传感器
step/assembly/*.step                               含所有螺丝和螺母的装配体，装配教程用的就是这些文件，
                                                   包括主手的指环指尖
stl/*.stl                                          打印件，每种零件一个文件，单位 mm
BOM.md / BOM_zh.md                                 物料清单
assembly/                                          分步装配教程
force_calibration.md / force_calibration_zh.md     指尖力传感器标定方法
```

三个整手 STEP 都包含 Franka 法兰转接件和手眼相机支架。

## 装配 STEP

每个 STEP 文件都是 AP214 装配体，每个零件都是单独命名的实体。SolidWorks、Fusion、FreeCAD、Onshape 等 CAD 软件都能打开。

零件名和下面的 STL 文件名一致。

模型是 CAD 姿态，三根手指平行。真实手的标定零位和它不同，见 [`../sim/README_zh.md`](../sim/README_zh.md#零位)。

## 打印件

所有结构件都用 PLA 打印。每个文件按表里的数量打印。

| 文件 | 数量 | 零件 |
|---|---|---|
| `hand-base.stl` | 1 | 手掌，装三个 CMC1 舵机 |
| `hand_connector.stl` | 1 | 连接手掌和法兰转接件 |
| `franka_flange.stl` | 1 | Franka Emika 法兰转接件 |
| `CMC1_left_joint.stl` | 1 | CMC1 支架，左指 |
| `CMC1_mid_right_joint.stl` | 2 | CMC1 支架，中指和右指 |
| `CMC2_joints.stl` | 3 | CMC2 支架 |
| `MCP_joints.stl` | 3 | MCP 连杆 |
| `IP_joints.stl` | 3 | IP 连杆 |
| `fingertip_joints.stl` | 3 | 末端连杆，装指尖传感器 |
| `force_sensor_layer1.stl` | 6 | 指尖传感器板，每指两块；内板打印时埋入三颗 M3 螺母 |
| `left_finger_nail.stl` | 1 | 楔形指尖，左指 |
| `mid_finger_nail.stl` | 1 | 楔形指尖，中指 |
| `right_finger_nail.stl` | 1 | 楔形指尖，右指 |
| `mushroom_finger.stl` | 3 | 蘑菇头指尖，可以包海绵或湿巾（替代指甲和传感器） |
| `controller_finger.stl` | 3 | 主手的指环指尖（替代指甲和传感器）；打印时每个埋入三颗 M3 螺母 |
| `hand_eye_cam_mount.stl` | 1 | 手眼相机支臂（可选） |
| `camera_mount.stl` | 1 | 支臂末端的相机座（可选） |

## 外购件

| 零件 | 数量 | 说明 |
|---|---|---|
| 飞特 ST-3215-C018 串行总线舵机（12 V，30 kg·cm） | 12 | 每指 4 个 |
| 微型拉压力传感器（0–5 kg，M2.5） | 9 | 每个指尖 3 个；只有力传感版本需要 |

完整清单（电源、线材、变送器、相机和主手零件）见 [`BOM_zh.md`](BOM_zh.md)。

## 许可证

硬件设计文件采用 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh-hans) 许可（见 `LICENSE`）。可以自由制作、修改和分享，仅限非商业用途，需要署名并以相同许可证发布。商业用途请联系通讯作者。
