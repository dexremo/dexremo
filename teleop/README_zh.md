# DexRemo 遥操作

[English](README.md) | **中文**

DexRemo 灵巧手和主手的 Python 工具：设置舵机 ID、零位标定、读写关节、主从遥操作。力传感是可选的：没有力传感器也能运行，另外留了接口，接你自己的变送器。

关节名、零位和正方向都和[仿真模型](../sim/README_zh.md)一致。关节角的单位是弧度。

## 安装

需要 Python 3.10 及以上。

```bash
cd teleop
pip install -e .
```

装好后可以用 `dexremo-teleop` 命令。依赖只有 `numpy`、`pyserial` 和飞特舵机 SDK（`feetech-servo-sdk`）。

想要 3D 实时显示（`--viewer`、`view`）和腕部坐标系下的力，再装 MuJoCo：

```bash
pip install -e ".[viewer]"
```

**Linux：** 当前用户要有串口权限。运行下面这条命令一次，然后注销再重新登录：

```bash
sudo usermod -aG dialout $USER
```

## 1. 找串口

用 USB 接上灵巧手和主手的舵机驱动板，然后运行：

```bash
dexremo-teleop ports
```

拔掉一块板再运行一次，就能看出哪个串口对应哪个设备。下面的例子里，灵巧手在 `/dev/ttyACM0`，主手在 `/dev/ttyACM1`。请换成你自己的串口。

## 2. 设置舵机 ID

新舵机的 ID 都是 1。装进去之前，按[舵机 ID 表](../hardware/assembly/README_zh.md)给每个舵机设好 ID。驱动板上**一次只接一个舵机**：

```bash
dexremo-teleop set-id --port /dev/ttyACM0 --id 5
```

装好一整只手后检查一遍，12 个 ID 都应该有应答：

```bash
dexremo-teleop scan --port /dev/ttyACM0
```

## 3. 标定

装好之后，灵巧手和主手各标定一次。换了舵机或者拆过关节，要重新标定。

```bash
dexremo-teleop calibrate --port /dev/ttyACM0 --name follower
dexremo-teleop calibrate --port /dev/ttyACM1 --name leader
```

脚本会先关掉扭矩，然后带你做两步：

1. 把设备摆到[零位](../sim/README_zh.md)，按回车。脚本把这个姿态写进每个舵机，作为零位偏移，之后零位读数是 2048。
2. 把每个关节都在全行程内活动一遍，按回车。脚本记下每个关节的行程，遥操作时不会让灵巧手超出这个范围。

结果保存在 `~/.dexremo/calibration/<name>.json`。程序连接时会检查舵机里的偏移和这个文件是否一致，不一致会提示你重新标定。

## 4. 检查关节正方向

```bash
dexremo-teleop monitor --port /dev/ttyACM0 --name follower
```

在零位时，每个关节的读数应该接近 0°。按[关节表](../sim/README_zh.md)里的 +q 方向转动每个关节，读数应该变大。按装配教程装好的手，所有舵机的转向都和仿真模型一致，默认的正方向（全是 +1）不用改。手掌朝下安装时：

- `mcp`、`ip`：手指朝手掌方向（往上）抬为正；
- `cmc1`：从手背（法兰那一侧）往下看，逆时针转为正；
- `cmc2`：从外面朝手掌中心看，顺时针转为正。

对照[关节方向图](../sim/docs/joint_convention.png)看最直观。

如果某个关节方向反了（比如舵机装反了），就在标定文件里把它的 `"sign"` 改成 `-1`。

正方向会影响录下来的数据，也决定能不能和仿真模型对上。遥操作是把主手的关节角直接映射到灵巧手上，所以只要两边的正方向设置一样，灵巧手都能正确跟随。

## 5. 遥操作

```bash
dexremo-teleop teleop --leader-port /dev/ttyACM1 --follower-port /dev/ttyACM0
```

- 开始时，灵巧手会慢慢移动到主手的姿态（`--ramp`，默认 2 秒），然后以 30 Hz 跟随主手（`--fps`）。
- 指令会被限制在每个关节的标定行程内（留 `--margin` 个刻度的余量），关节速度也有上限（`--max-speed`，单位 rad/s）。
- 按 Ctrl+C 停止。停止后灵巧手的扭矩会关掉；如果想保持扭矩，加 `--hold`。
- 加 `--viewer` 会打开一个 3D 窗口，实时显示灵巧手的姿态和指尖力箭头（右指红、中指绿、左指蓝，箭头长度每牛顿 2.5 cm）。显示在单独的线程里，不影响控制频率。
- 只想看一个设备、不做遥操作（扭矩关闭，用手掰）：`dexremo-teleop view --port /dev/ttyACM1 --name leader`。

## 力传感器

如果没有力传感指尖，`--force` 用默认的 `none` 就行。

没有传感器也可以先试显示和数据流程：`--force mock` 会生成模拟的指尖力。

```bash
dexremo-teleop teleop --leader-port /dev/ttyACM1 --follower-port /dev/ttyACM0 --viewer --force mock
```

代码里没有针对某一款变送器的驱动。要用力传感指尖，按下面几步做：

1. 复制 [`examples/my_transmitter.py`](examples/my_transmitter.py)，照着变送器的说明书填好 `read_channels()` 和 `zero()`。`read_channels()` 要按[标定方法](../hardware/force_calibration_zh.md)里的通道顺序（1+X、1+Y、1−Y、2+X……）返回 9 个读数；`zero()` 发送说明书里的清零命令。
2. 每天开机后清零一次（指尖不要碰任何东西），然后检查读数：
   ```bash
   dexremo-teleop force-zero --force my_transmitter.py:MyTransmitter
   dexremo-teleop force-check --force my_transmitter.py:MyTransmitter
   ```
   不要频繁清零：每次清零都会写变送器单片机的存储器，写入次数有限。
3. 把标定方法第 6 步里每个指尖拟合出来的结果写进一个 JSON 文件：
   ```json
   {"right": {"K": [[...], [...], [...]], "c": [0, 0, 0]}, "mid": {...}, "left": {...}}
   ```
4. 带上力传感器做遥操作：
   ```bash
   dexremo-teleop teleop ... --force my_transmitter.py:MyTransmitter --force-calibration my_force_calib.json
   ```

终端里同时显示每个指尖传感器坐标系下的力和腕部坐标系下的力（F_wrist = R(q)·F_sensor，R 由仿真模型的正运动学算出；需要装 MuJoCo）。传感器在单独的线程里读取，变送器慢也不会拖慢遥操作。

你也可以自己写一个类，只要继承 [`dexremo_teleop/force.py`](dexremo_teleop/force.py) 里的 `ForceSensor`，并为每个指尖返回一个力，就能用。

## 在 Python 里调用

```python
from dexremo_teleop import Hand, JOINT_NAMES, load_calibration

hand = Hand("/dev/ttyACM0", load_calibration("follower"))
hand.connect()
q = hand.read_q()                 # 12 个关节角，单位弧度，顺序同 JOINT_NAMES
hand.configure_follower()
hand.set_torque(True)
hand.write_q(q)                   # 会被限制在标定行程内
hand.disconnect()
```

## 还没有的功能

- 录制示教数据。

## 许可

MIT（见 [`LICENSE`](LICENSE)）。
