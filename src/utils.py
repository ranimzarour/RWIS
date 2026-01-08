# utils.py
from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional

import numpy as np


def safe_unit_quat(q: np.ndarray) -> np.ndarray:
    """Normalise un quaternion (si norme ~0 => identité)."""
    q = np.asarray(q, dtype=np.float32).reshape(4,)
    n = float(np.linalg.norm(q))
    if not np.isfinite(n) or n < 1e-8:
        return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    return (q / n).astype(np.float32)


def quaternion_distance(q1: np.ndarray, q2: np.ndarray) -> float:
    """
    Distance angulaire robuste entre deux quaternions.
    - Accepte wxyz OU xyzw via un "min" entre les deux hypothèses (heuristique robuste).
    - Retourne une distance normalisée dans [0, 1] (0 parfait, 1 très mauvais).
    """
    q1 = np.asarray(q1, dtype=np.float32).reshape(4,)
    q2 = np.asarray(q2, dtype=np.float32).reshape(4,)

    # Deux hypothèses: [w,x,y,z] ou [x,y,z,w]
    q1_wxyz = safe_unit_quat(q1)
    q2_wxyz = safe_unit_quat(q2)

    q1_xyzw = safe_unit_quat(np.array([q1[3], q1[0], q1[1], q1[2]], dtype=np.float32))
    q2_xyzw = safe_unit_quat(np.array([q2[3], q2[0], q2[1], q2[2]], dtype=np.float32))

    def _angle(a: np.ndarray, b: np.ndarray) -> float:
        dot = float(np.abs(np.dot(a, b)))
        dot = float(np.clip(dot, -1.0, 1.0))
        ang = float(np.arccos(dot))  # [0, pi/2]
        return ang

    ang1 = _angle(q1_wxyz, q2_wxyz)
    ang2 = _angle(q1_xyzw, q2_xyzw)

    ang = min(ang1, ang2)

    # normalisation: max théorique ~ pi/2
    return float(np.clip(ang / (math.pi / 2.0), 0.0, 1.0))


def normalize_positions(positions: Mapping[str, np.ndarray]) -> Dict[str, np.ndarray]:
    """
    Retire la translation globale (hips à l'origine).
    Si "Hips" absent: utilise le premier joint disponible, sinon (0,0,0).
    """
    if not positions:
        return {}

    if "Hips" in positions:
        root = np.asarray(positions["Hips"], dtype=np.float32)
    else:
        # fallback: premier joint
        first_key = next(iter(positions.keys()))
        root = np.asarray(positions[first_key], dtype=np.float32)

    return {j: (np.asarray(p, dtype=np.float32) - root) for j, p in positions.items()}


def low_pass_filter(signal: np.ndarray, alpha: float = 0.8) -> np.ndarray:
    """
    Filtre passe-bas exponentiel.
    - Retourne np.ndarray
    - Gère signal vide
    """
    sig = np.asarray(signal, dtype=np.float32)
    if sig.size == 0:
        return sig

    out = np.empty_like(sig, dtype=np.float32)
    out[0] = sig[0]
    for i in range(1, len(sig)):
        out[i] = alpha * out[i - 1] + (1.0 - alpha) * sig[i]
    return out


def compute_grade(score: float) -> str:
    s = float(score)
    if s >= 0.85:
        return "Perfect"
    if s >= 0.70:
        return "Good"
    if s >= 0.50:
        return "OK"
    return "Miss"


def _to_f32_array(x: Any) -> np.ndarray:
    return np.asarray(x, dtype=np.float32)


def json_to_motion_data(json_data: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Conversion JSON -> structure interne.
    - Ne crashe pas si une clé manque: met des valeurs par défaut.
    """
    timestamp = json_data.get("timestamp", 0.0)

    rotations_in = json_data.get("rotations", {}) or {}
    rotations = {}
    if isinstance(rotations_in, Mapping):
        for joint, quat in rotations_in.items():
            try:
                rotations[joint] = _to_f32_array(quat).reshape(4,)
            except Exception:
                # ignore entrée invalide
                continue

    traj_in = json_data.get("trajectories", {}) or {}
    trajectories = {}
    if isinstance(traj_in, Mapping):
        for joint, traj in traj_in.items():
            if traj is None:
                continue
            try:
                trajectories[joint] = [ _to_f32_array(p).reshape(3,) for p in traj ]
            except Exception:
                continue

    rhythm_signal = json_data.get("rhythm_signal", [])
    try:
        rhythm_signal = _to_f32_array(rhythm_signal)
    except Exception:
        rhythm_signal = np.asarray([], dtype=np.float32)

    return {
        "timestamp": timestamp,
        "rotations": rotations,
        "trajectories": trajectories,
        "rhythm_signal": rhythm_signal,
    }
