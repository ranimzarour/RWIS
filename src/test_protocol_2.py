# test_protocol_2.py
import json
from main import process_mocopi_message


def make_mocopi_frame(fnum: int, t_ns: int, l_pos, r_pos, l_rot, r_rot):
    """
    Cette fonction crée un frame simulé de mocopi avec des positions et des rotations pour le joueur et la référence.
    """
    return {
        "fnum": fnum,
        "time": t_ns,
        "bones": {
            "l_hand": {"rot_xyzw": l_rot, "pos_xyz": l_pos},
            "r_hand": {"rot_xyzw": r_rot, "pos_xyz": r_pos},
        },
    }


def run_test_10_frames():
    """
    Teste le calcul des scores pour 10 frames avec des données simulées.
    """
    base_time = 1_063_675_480  # timestamp de départ (ns)
    step = 16_666_667  # ~60 FPS en ns

    for i in range(10):
        t = base_time + i * step

        # Données pour la référence (mouvement lent)
        ref_frame = make_mocopi_frame(
            fnum=i,
            t_ns=t,
            l_pos=[0.25 + 0.001*i, 0.0005, 0.0012],
            r_pos=[-0.25 - 0.001*i, 0.0005, 0.0012],
            l_rot=[0.84, -0.29, -0.02, -0.43],
            r_rot=[-0.79, -0.03,  0.08,  0.59],
        )

        # Données pour le joueur (mouvement plus important)
        player_frame = make_mocopi_frame(
            fnum=i,
            t_ns=t,
            l_pos=[0.25 + 0.003*i, 0.0005, 0.0012],
            r_pos=[-0.25 - 0.003*i, 0.0005, 0.0012],
            l_rot=[0.84, -0.29, -0.02, -0.43],
            r_rot=[-0.79, -0.03,  0.08,  0.59],
        )

        # Conversion des frames de mocopi en JSON (brut) pour player et ref
        player_json = json.dumps(player_frame)
        ref_json = json.dumps(ref_frame)

        # Appel de la fonction qui va tout adapter, accumuler, et calculer les scores
        response = process_mocopi_message(player_json, ref_json)
        result = json.loads(response)

        if not result.get("ok", False):
            raise RuntimeError(f"Frame {i}: scoring failed -> {result}")

        # Affichage des résultats pour chaque frame
        print(
            f"Frame {i}: final={result['final']:.3f} pose={result['pose']:.3f} "
            f"traj={result['trajectory']:.3f} rhythm={result['rhythm']:.3f} "
            f"grade={result['grade']} traj_valid={result.get('trajectory_valid')} dtw_cost={result.get('dtw_cost')}"
        )


if __name__ == "__main__":
    run_test_10_frames()
