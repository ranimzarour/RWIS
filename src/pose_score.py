# pose_score.py
from __future__ import annotations

import numpy as np

from config import JOINT_WEIGHTS
from utils import quaternion_distance


def compute_pose_score(player_rot: dict, ref_rot: dict) -> float:
    """
    Score de pose dans [0, 1]
    - robuste aux joints manquants
    - évite division par zéro
    - distance quaternion normalisée
    """
    if not isinstance(player_rot, dict) or not isinstance(ref_rot, dict):
        return 0.0

    total = 0.0
    weight_sum = 0.0

    for joint, w in JOINT_WEIGHTS.items():
        if joint not in player_rot or joint not in ref_rot:
            continue

        d = quaternion_distance(player_rot[joint], ref_rot[joint])  # d in [0,1]
        if not np.isfinite(d):
            continue

        total += float(w) * float(d)
        weight_sum += float(w)

    if weight_sum <= 1e-8:
        return 0.0

    avg = total / weight_sum  # 0..1
    score = 1.0 - avg
    return float(np.clip(score, 0.0, 1.0))
