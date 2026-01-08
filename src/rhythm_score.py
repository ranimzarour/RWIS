# rhythm_score.py
from __future__ import annotations

import numpy as np


def _as_2d(x: np.ndarray) -> np.ndarray:
    """
    Convertit x en:
    - (T, D) si possible
    - si 1D -> (T, 1)
    """
    a = np.asarray(x, dtype=np.float32)
    if a.ndim == 0:
        return a.reshape(1, 1)
    if a.ndim == 1:
        return a.reshape(-1, 1)
    if a.ndim == 2:
        return a
    # au-delà: on écrase tout sauf T
    return a.reshape(a.shape[0], -1)


def compute_velocity(signal: np.ndarray) -> np.ndarray:
    s = _as_2d(signal)
    if len(s) < 2:
        return np.zeros((0, s.shape[1]), dtype=np.float32)
    return np.diff(s, axis=0)


def compute_rhythm_score(player_signal: np.ndarray, ref_signal: np.ndarray) -> float:
    """
    Compare les vitesses (approx rythme).
    Robustesse:
    - 1D ou 2D
    - gère séquences trop courtes
    - aligne sur la plus petite longueur
    Retour: [0,1]
    """
    pv = compute_velocity(player_signal)
    rv = compute_velocity(ref_signal)

    if pv.shape[0] == 0 or rv.shape[0] == 0:
        # pas assez de données: neutre (pas perfect)
        return 0.5

    # norme frame-by-frame
    p = np.linalg.norm(pv, axis=1)
    r = np.linalg.norm(rv, axis=1)

    n = min(len(p), len(r))
    if n == 0:
        return 0.5

    p = p[:n]
    r = r[:n]

    err = float(np.mean(np.abs(p - r)))
    if not np.isfinite(err):
        return 0.0

    # normalisation légère: évite qu'une échelle (cm vs m) casse tout
    denom = float(np.mean(np.abs(r)) + 1e-6)
    err_norm = err / denom  # ~0 si bon

    score = float(np.exp(-err_norm))
    return float(np.clip(score, 0.0, 1.0))
