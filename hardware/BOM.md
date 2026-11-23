# DexRemo bill of materials

**English** | [中文](BOM_zh.md)

Bought parts for the DexRemo hand (the follower), the leader device used for teleoperation, and the camera setup used in the paper. Printed parts are listed in [`README.md`](README.md#printed-parts).

Links point to the shops the authors bought from. Equivalent parts from other suppliers work as well, as long as the specification matches.

## Follower hand

| Part | Specification | Qty | Link |
|---|---|---|---|
| Serial bus servo | Feetech ST-3215-C018, 12 V, 30 kg·cm, 1:345 gear ratio | 12 | [Taobao](https://item.taobao.com/item.htm?id=712179366565&skuId=5268252241438) |
| Power supply | 12 V, 8 A | 1 | [Taobao](https://item.taobao.com/item.htm?id=544824248494) |
| Servo driver board | Connects the servo bus to the PC over USB | 1 | [Tmall](https://detail.tmall.com/item.htm?id=738817173460&skuId=5096283384143) |
| Servo cable | 3-pin, 200 mm | 5 | [Taobao](https://item.taobao.com/item.htm?id=607253676830) |
| Miniature tension/compression load cell | 0–5 kg, M2.5 thread | 9 | [Taobao](https://item.taobao.com/item.htm?id=572636578877&skuId=3893609319890) |
| Load-cell transmitter | One 12-channel unit (9 channels are used). Two smaller units also work but cost about the same | 1 (12-ch) | [Taobao](https://item.taobao.com/item.htm?id=555869772245&skuId=4525021828639) |
| RS485–USB adapter | CP2102, 1.5 m (UT-891); one per transmitter | 1 per transmitter | [Tmall](https://detail.tmall.com/item.htm?id=35733422585) |
| Screws and bolts | See [Fasteners](#fasteners) | | |

## Leader device

| Part | Specification | Qty | Link |
|---|---|---|---|
| Serial bus servo | Feetech ST-3215-C001, 7.4 V, 19 kg·cm, 1:345 gear ratio | 12 | [Taobao](https://item.taobao.com/item.htm?id=712179366565&skuId=5268252241438) |
| Power supply | 5 V, 5 A | 1 | [Taobao](https://item.taobao.com/item.htm?id=544824248494) |
| Servo driver board | Connects the servo bus to the PC over USB | 1 | [Tmall](https://detail.tmall.com/item.htm?id=738817173460&skuId=5096283384143) |
| Servo cable | 3-pin, 200 mm | 5 | [Taobao](https://item.taobao.com/item.htm?id=607253676830) |
| Printed parts | Same as the hand, with `controller_finger.stl` (x3) in place of the nails and fingertip sensors; no connector, flange adapter or camera mount | | |
| Screws and bolts | As for the hand without force sensing; see [Fasteners](#fasteners) | | |

## Cameras

The paper uses one wrist camera (on the printed camera mount) and two external cameras.

| Part | Specification | Qty | Link |
|---|---|---|---|
| RGB camera | USB | 3 | [Taobao](https://item.taobao.com/item.htm?id=740242931183) |
| USB hub | | 1 | [Tmall](https://detail.tmall.com/item.htm?id=625891815911) |

## Calibration tools

| Part | Specification | Qty | Link |
|---|---|---|---|
| Slotted calibration weight set | 100 mg – 1 kg, 17 pieces, with 100 g weight hanger | 1 | [Taobao](https://item.taobao.com/item.htm?id=37924053620&skuId=4667036203958) |

How to use them: [force-sensor calibration method](force_calibration.md).

## Fasteners

Counts for one follower hand with force-sensing fingertips, taken from the assembly STEP. The [assembly guide](assembly/README.md) shows where each one goes.

| Fastener | Qty | Where |
|---|---|---|
| M3×6 countersunk screw | 84 | Servo horns: 28 per finger |
| ST2.2×4.5 self-tapping screw | 48 | Servo bodies into their brackets: 4 per servo |
| M3×12 screw | 12 | Fingers onto the palm: 4 per finger |
| M3×6 cheese-head screw | 9 | Fingertips onto the distal links: 3 per finger |
| M3 hex nut | 21 | 4 in each CMC1 housing; 3 in each fingertip: embedded in the sensor inner plate while printing |
| M2.5×3 screw | 18 | Fingertip sensor plates to the load cells: 6 per finger |

Without force sensing, the M2.5 screws are not needed, and the 9 fingertip nuts go into the fingernails after printing.

The leader device uses the same fasteners as a hand without force sensing; its fingertip nuts go into the rings after printing. Mount the leader on a stand of your choice.

**Not counted above**
- The connector, the flange adapter, the camera mount and the leader device are fixed with M2–M4 screws; choose lengths to suit your prints.
- Fixing the hand to the Franka flange also needs screws.

## Notes

- **Servo versions.** Both servo versions are sold on the same page; choose the version in the shop's options. The follower needs the 12 V ST-3215-C018. The 7.4 V ST-3215-C001 is only for the leader device.
- **Power supplies.** Both power supplies are also sold on the same page.
