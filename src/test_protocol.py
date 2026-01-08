# test_protocol.py
import json
import numpy as np
from typing import Optional


from main import process_unity_message, reset_state, extract_dtw_feature
from utils import json_to_motion_data


# -----------------------------
# Helpers pour data fictives
# -----------------------------
def quat_identity():
    return [1.0, 0.0, 0.0, 0.0]


def quat_y_180_wxyz():
    # rotation 180° autour de Y en wxyz (w=0, y=1)
    return [0.0, 0.0, 1.0, 0.0]


def make_reference(T=60):
    # Trajectoires simples : mains bougent en sinusoïde sur X
    t = np.linspace(0, 2 * np.pi, T).astype(np.float32)
    lh = np.stack([0.2 * np.sin(t), np.zeros_like(t), np.zeros_like(t)], axis=1)
    rh = np.stack([0.2 * np.sin(t), np.zeros_like(t), np.zeros_like(t)], axis=1)

    # rhythm_signal : un signal 1D
    rhythm = np.sin(4 * t).astype(np.float32)

    ref = {
        "timestamp": 0.0,
        "rotations": {
            "Hips": quat_identity(),
            "LeftHand": quat_identity(),
            "RightHand": quat_identity(),
        },
        "trajectories": {
            "LeftHand": lh.tolist(),
            "RightHand": rh.tolist(),
        },
        "rhythm_signal": rhythm.tolist(),
    }
    return ref


def make_player_frame_from_ref(
    ref, k, pose_variant="same", traj_offset=(0, 0, 0), rhythm_variant="same"
):
    # rotations
    if pose_variant == "same":
        rots = ref["rotations"]
    elif pose_variant == "bad_hands":
        rots = dict(ref["rotations"])
        rots["LeftHand"] = quat_y_180_wxyz()
        rots["RightHand"] = quat_y_180_wxyz()
    else:
        rots = ref["rotations"]

    # trajectoires (on envoie l'historique jusqu'à k)
    lh_full = np.array(ref["trajectories"]["LeftHand"], dtype=np.float32)[: k + 1]
    rh_full = np.array(ref["trajectories"]["RightHand"], dtype=np.float32)[: k + 1]
    offset = np.array(traj_offset, dtype=np.float32).reshape(1, 3)
    lh_full = lh_full + offset
    rh_full = rh_full + offset

    traj = {
        "LeftHand": lh_full.tolist(),
        "RightHand": rh_full.tolist(),
    }

    # rhythm
    if rhythm_variant == "same":
        rhythm = np.array(ref["rhythm_signal"], dtype=np.float32)[: k + 1]
    elif rhythm_variant == "phase_shift":
        base = np.array(ref["rhythm_signal"], dtype=np.float32)
        rhythm = np.roll(base, 5)[: k + 1]
    elif rhythm_variant == "flat":
        rhythm = np.zeros((k + 1,), dtype=np.float32)
    else:
        rhythm = np.array(ref["rhythm_signal"], dtype=np.float32)[: k + 1]

    player = {
        "timestamp": float(k) / 60.0,
        "rotations": rots,
        "trajectories": traj,
        "rhythm_signal": rhythm.tolist(),
    }
    return player


def run_sequence_test(
    ref, pose_variant="same", traj_offset=(0, 0, 0), rhythm_variant="same", T=60
):
    reset_state()
    ref_np = json_to_motion_data(ref)

    outputs = []
    for k in range(T):
        player = make_player_frame_from_ref(
            ref,
            k,
            pose_variant=pose_variant,
            traj_offset=traj_offset,
            rhythm_variant=rhythm_variant,
        )
        out = process_unity_message(json.dumps(player), ref_np)
        outputs.append(json.loads(out))
    return outputs


# -----------------------------
# Debug helpers (Option A)
# -----------------------------
def feat_status(x: Optional[np.ndarray]) -> str:
    if x is None:
        return "None"
    if np.allclose(x, 0):
        return "all_zero"
    return "ok"


def debug_features(label: str, player_json_dict: dict, ref_np: dict):
    """
    Affiche les features DTW (ou leur status) pour comprendre
    les cas Missing keys / Empty hands / NaN frame.
    """
    player_np = json_to_motion_data(player_json_dict)

    pf = extract_dtw_feature(player_np)
    rf = extract_dtw_feature(ref_np)

    print(f"\nDEBUG {label}:")
    print("  player_feat_status:", feat_status(pf))
    print("  ref_feat_status   :", feat_status(rf))
    print("  player_feat       :", pf)
    print("  ref_feat          :", rf)


# -----------------------------
# TESTS
# -----------------------------
if __name__ == "__main__":
    ref = make_reference(T=60)

    # 1) Perfect match
    out = run_sequence_test(ref, "same", (0, 0, 0), "same")
    print("Perfect last:", out[-1])

    # 2) Pose error only
    out = run_sequence_test(ref, "bad_hands", (0, 0, 0), "same")
    print("Bad pose last:", out[-1])

    # 3) Trajectory error only (offset mains)
    out = run_sequence_test(ref, "same", (0.5, 0, 0), "same")
    print("Bad traj last:", out[-1])

    # 4) Rhythm error only
    out = run_sequence_test(ref, "same", (0, 0, 0), "phase_shift")
    print("Bad rhythm last:", out[-1])

    # Prépare ref en "numpy dict" pour les tests unitaires ci-dessous
    reset_state()
    ref_np = json_to_motion_data(ref)

    # 5) JSON invalide
    out = process_unity_message("{not a json", ref_np)
    print("Invalid JSON:", out)

    # 6) Clés manquantes
    reset_state()
    minimal = {"timestamp": 0.0}  # pas rotations / trajectories / rhythm_signal
    debug_features("Missing keys", minimal, ref_np)
    out = process_unity_message(json.dumps(minimal), ref_np)
    print("Missing keys:", out)

    # 7) Listes vides mains
    reset_state()
    empty_hands = {
        "timestamp": 0.0,
        "rotations": {"Hips": quat_identity()},
        "trajectories": {"LeftHand": [], "RightHand": []},
        "rhythm_signal": [0.0],
    }
    debug_features("Empty hands", empty_hands, ref_np)
    out = process_unity_message(json.dumps(empty_hands), ref_np)
    print("Empty hands:", out)

    # 8) NaN / Inf dans trajectoire (frame ignorée DTW)
    reset_state()
    nan_frame = make_player_frame_from_ref(ref, 10, "same", (0, 0, 0), "same")
    nan_frame["trajectories"]["LeftHand"][-1] = [float("nan"), 0.0, 0.0]
    debug_features("NaN frame", nan_frame, ref_np)
    out = process_unity_message(json.dumps(nan_frame), ref_np)
    print("NaN frame:", out)

    # 9) Reset commande
    reset_state()
    out = process_unity_message(json.dumps({"command": "reset"}), ref_np)
    print("Reset cmd:", out)
