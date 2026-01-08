# main.py
from __future__ import annotations

import json
from typing import Any, Dict, Optional

import numpy as np

from pose_score import compute_pose_score
from rhythm_score import compute_rhythm_score
from config import POSE_WEIGHT, TRAJECTORY_WEIGHT, RHYTHM_WEIGHT, WINDOW_SIZE
from utils import compute_grade, json_to_motion_data
from dtw_online import SlidingDTW

from mocopi_adapter import adapt_mocopi_frame, reset_adapter_state


# ============================================================
# GLOBAL SCORING STATE (DTW) + reset
# ============================================================
dtw_trajectory = SlidingDTW(window_size=WINDOW_SIZE, band=8)


def reset_state() -> None:
    dtw_trajectory.reset()
    reset_adapter_state()


# ============================================================
# DTW FEATURE EXTRACTION
# ============================================================
def extract_dtw_feature(data: Dict[str, Any]) -> Optional[np.ndarray]:
    traj = data.get("trajectories") or {}
    if not isinstance(traj, dict):
        return None

    lh_list = traj.get("LeftHand")
    rh_list = traj.get("RightHand")

    if not isinstance(lh_list, list) or not isinstance(rh_list, list):
        return None
    if len(lh_list) == 0 or len(rh_list) == 0:
        return None

    try:
        lh = np.asarray(lh_list[-1], dtype=np.float32).reshape(3,)
        rh = np.asarray(rh_list[-1], dtype=np.float32).reshape(3,)
    except Exception:
        return None

    if not (np.all(np.isfinite(lh)) and np.all(np.isfinite(rh))):
        return None

    return np.concatenate([lh, rh], axis=0)


# ============================================================
# PURE SCORING: expects scoring-format JSON for player + ref
# ============================================================
def process_unity_message(json_string: str, ref_data: Dict[str, Any]) -> str:
    try:
        raw = json.loads(json_string)

        # reset command for scoring-format calls
        if isinstance(raw, dict) and (raw.get("reset") is True or raw.get("command") == "reset"):
            reset_state()
            return json.dumps({"ok": True, "reset": True})

        player_data = json_to_motion_data(raw)

        if "rotations" not in ref_data or "trajectories" not in ref_data:
            ref_data = json_to_motion_data(ref_data)

        pose = compute_pose_score(player_data.get("rotations", {}), ref_data.get("rotations", {}))

        player_feat = extract_dtw_feature(player_data)
        ref_feat = extract_dtw_feature(ref_data)

        if player_feat is None or ref_feat is None:
            trajectory = 0.5
            dtw_cost = None
            trajectory_valid = False
        else:
            dtw_trajectory.add_frame(player_feat, ref_feat)
            dtw_cost = dtw_trajectory.compute()
            trajectory = float(np.exp(-float(dtw_cost)))
            trajectory = float(np.clip(trajectory, 0.0, 1.0))
            trajectory_valid = True

        rhythm = compute_rhythm_score(
            player_data.get("rhythm_signal", np.asarray([], dtype=np.float32)),
            ref_data.get("rhythm_signal", np.asarray([], dtype=np.float32)),
        )

        final_score = (
            POSE_WEIGHT * float(pose) +
            TRAJECTORY_WEIGHT * float(trajectory) +
            RHYTHM_WEIGHT * float(rhythm)
        )
        final_score = float(np.clip(final_score, 0.0, 1.0))
        grade = compute_grade(final_score)

        return json.dumps({
            "final": final_score,
            "pose": float(pose),
            "trajectory": float(trajectory),
            "rhythm": float(rhythm),
            "grade": grade,
            "ok": True,
            "trajectory_valid": trajectory_valid,
            "dtw_cost": (None if dtw_cost is None else float(dtw_cost)),
        })

    except Exception as e:
        return json.dumps({
            "ok": False,
            "error": str(e),
            "final": 0.0,
            "pose": 0.0,
            "trajectory": 0.0,
            "rhythm": 0.0,
            "grade": "Miss"
        })


# ============================================================
# WRAPPER: mocopi raw JSON (player+ref) -> scoring -> output JSON
# ============================================================
def process_mocopi_message(mocopi_player_json: str, mocopi_ref_json: str) -> str:
    """
    This is your recommended entry point for the pipeline:
    - input: raw mocopi JSON strings (player & ref)
    - output: score JSON string

    It uses mocopi_adapter to transform both streams into the scoring-format input,
    with internal trajectory accumulation, then calls process_unity_message().
    """
    try:
        player_raw = json.loads(mocopi_player_json)
        ref_raw = json.loads(mocopi_ref_json)

        # If either side asks for reset, reset everything
        if (isinstance(player_raw, dict) and player_raw.get("command") == "reset") or \
           (isinstance(ref_raw, dict) and ref_raw.get("command") == "reset"):
            reset_state()
            return json.dumps({"ok": True, "reset": True})

        # Adapt raw mocopi -> scoring-format dicts
        player_scoring = adapt_mocopi_frame(player_raw, stream="player", max_len=WINDOW_SIZE)
        ref_scoring = adapt_mocopi_frame(ref_raw, stream="ref", max_len=WINDOW_SIZE)

        # Score
        return process_unity_message(json.dumps(player_scoring), ref_scoring)

    except Exception as e:
        return json.dumps({
            "ok": False,
            "error": f"process_mocopi_message failed: {e}",
            "final": 0.0,
            "pose": 0.0,
            "trajectory": 0.0,
            "rhythm": 0.0,
            "grade": "Miss"
        })
