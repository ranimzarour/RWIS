# mocopi_adapter.py
from __future__ import annotations
from typing import Dict, Any

# Histories stored per stream
_histories: Dict[str, Dict[str, list]] = {
    "player": {},
    "ref": {},
}

_NAME_MAP = {
    "l_hand": "LeftHand",
    "r_hand": "RightHand",
    # add more bones later if you want pose scoring beyond hands:
    # "root": "Hips",
    # "torso_1": "Spine",
}

def reset_adapter_state() -> None:
    _histories["player"].clear()
    _histories["ref"].clear()

def adapt_mocopi_frame(mocopi_frame: Dict[str, Any], stream: str, max_len: int = 60) -> Dict[str, Any]:
    """
    Convert ONE mocopi frame (raw mocopi JSON dict) into the scoring-format JSON dict.
    Keeps an internal sliding history (trajectories) per stream ("player" or "ref").
    Output is JSON-serializable (pure python lists/floats).
    """
    if stream not in _histories:
        raise ValueError(f"stream must be 'player' or 'ref', got: {stream}")

    history = _histories[stream]

    t_ns = mocopi_frame.get("time", 0)
    timestamp = float(t_ns) / 1e9

    bones = mocopi_frame.get("bones", {}) or {}
    rotations = {}
    trajectories = {}

    for bone_name, bone_data in bones.items():
        if bone_name not in _NAME_MAP:
            continue
        joint = _NAME_MAP[bone_name]

        rot = bone_data.get("rot_xyzw", None)
        pos = bone_data.get("pos_xyz", None)

        if not (isinstance(rot, list) and len(rot) == 4 and isinstance(pos, list) and len(pos) == 3):
            continue

        rot_list = [float(rot[0]), float(rot[1]), float(rot[2]), float(rot[3])]
        pos_list = [float(pos[0]), float(pos[1]), float(pos[2])]

        rotations[joint] = rot_list

        if joint not in history:
            history[joint] = []
        history[joint].append(pos_list)
        if len(history[joint]) > max_len:
            history[joint] = history[joint][-max_len:]

        trajectories[joint] = history[joint]

    return {
        "timestamp": timestamp,
        "rotations": rotations,
        "trajectories": trajectories,
        "rhythm_signal": [],  # optional later
    }
