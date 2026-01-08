# trajectory_score.py (Inutile)
from __future__ import annotations

import numpy as np

EFFECTORS = ["LeftHand", "RightHand", "LeftFoot", "RightFoot"]


def compute_trajectory_score(player_traj: dict, ref_traj: dict) -> float:
    """
    Score [0,1] basé sur erreur moyenne entre trajectoires.
    Robuste aux clés manquantes / tailles différentes.
    """
    if not isinstance(player_traj, dict) or not isinstance(ref_traj, dict):
        return 0.0

    error = 0.0
    count = 0

    for eff in EFFECTORS:
        if eff not in player_traj or eff not in ref_traj:
            continue

        p_list = player_traj.get(eff) or []
        r_list = ref_traj.get(eff) or []
        n = min(len(p_list), len(r_list))
        if n <= 0:
            continue

        for k in range(n):
            p = np.asarray(p_list[k], dtype=np.float32).reshape(3,)
            r = np.asarray(r_list[k], dtype=np.float32).reshape(3,)
            if not (np.all(np.isfinite(p)) and np.all(np.isfinite(r))):
                continue
            error += float(np.linalg.norm(p - r))
            count += 1

    if count == 0:
        return 0.0

    avg_error = error / count

    # normalisation douce: score dans [0,1]
    score = float(np.exp(-avg_error))
    return float(np.clip(score, 0.0, 1.0))
