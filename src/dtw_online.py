# dtw_online.py
from __future__ import annotations

from typing import List, Optional

import numpy as np


class SlidingDTW:
    """
    DTW bandé recalculé sur fenêtre glissante.
    - Correct DP
    - band (Sakoe-Chiba) pour tolérance au retard
    - resettable
    """

    def __init__(self, window_size: int = 60, band: int = 8):
        self.W = int(window_size)
        self.band = int(band)
        self.player_buffer: List[np.ndarray] = []
        self.ref_buffer: List[np.ndarray] = []

    def reset(self) -> None:
        self.player_buffer.clear()
        self.ref_buffer.clear()

    def add_frame(self, player_feat: np.ndarray, ref_feat: np.ndarray) -> None:
        pf = np.asarray(player_feat, dtype=np.float32).reshape(-1,)
        rf = np.asarray(ref_feat, dtype=np.float32).reshape(-1,)

        # si dimensions incompatibles, on tronque au min pour éviter crash
        d = min(pf.shape[0], rf.shape[0])
        if d == 0:
            return
        pf = pf[:d]
        rf = rf[:d]

        # si NaN/inf -> ignore frame
        if not (np.all(np.isfinite(pf)) and np.all(np.isfinite(rf))):
            return

        self.player_buffer.append(pf)
        self.ref_buffer.append(rf)

        if len(self.player_buffer) > self.W:
            self.player_buffer.pop(0)
            self.ref_buffer.pop(0)

    def compute(self) -> float:
        n = len(self.player_buffer)
        if n == 0:
            return 0.0
        if n == 1:
            return float(np.linalg.norm(self.player_buffer[0] - self.ref_buffer[0]))

        # DP bandée: dp[i][j] mais stockée en 2 lignes
        inf = np.inf
        prev = np.full(n + 1, inf, dtype=np.float32)
        prev[0] = 0.0

        for i in range(1, n + 1):
            curr = np.full(n + 1, inf, dtype=np.float32)

            j_start = max(1, i - self.band)
            j_end = min(n, i + self.band)

            # pour que curr[j-1] soit valide dans la bande
            if j_start > 1:
                curr[j_start - 1] = inf

            for j in range(j_start, j_end + 1):
                cost = float(np.linalg.norm(self.player_buffer[i - 1] - self.ref_buffer[j - 1]))
                curr[j] = cost + min(
                    curr[j - 1],   # insertion
                    prev[j],       # deletion
                    prev[j - 1],   # match
                )

            prev = curr

        # normalisation par longueur (rend comparable)
        out = float(prev[n] / max(n, 1))
        if not np.isfinite(out):
            return 0.0
        return out
