"""Joint names, servo IDs and sign convention of the DexRemo hand.

Names and signs follow the simulation model (``sim/README.md``). Servo IDs follow
the assembly guide (``hardware/assembly/README.md#servo-id-map``): within each
finger, IDs run from the palm out to the fingertip.
"""

FINGERS = ("right", "mid", "left")
FINGER_JOINTS = ("cmc1", "cmc2", "mcp", "ip")

# Ordered by servo ID: right_cmc1 = 1, ..., left_ip = 12.
JOINT_NAMES = tuple(f"{finger}_{joint}" for finger in FINGERS for joint in FINGER_JOINTS)
SERVO_IDS = {name: i + 1 for i, name in enumerate(JOINT_NAMES)}

# +1 if a positive servo step moves the joint in the +q direction of the simulation
# model, -1 otherwise. A new calibration file starts from these values.
# Checked on the real hand and leader built as in the assembly guide: every servo
# turns the same way as the model, so all signs are +1. If you mount a servo the
# other way round, set that joint's sign to -1 in the calibration file.
DEFAULT_SIGNS = {name: 1 for name in JOINT_NAMES}
