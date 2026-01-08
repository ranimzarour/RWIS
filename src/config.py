# config.py

POSE_WEIGHT = 0.5
TRAJECTORY_WEIGHT = 0.3
RHYTHM_WEIGHT = 0.2

WINDOW_SIZE = 60   # ~1 seconde à 60 FPS

JOINT_WEIGHTS = {
    "Hips": 0.5,
    "Spine": 0.5,
    "LeftArm": 1.0,
    "RightArm": 1.0,
    "LeftLeg": 1.0,
    "RightLeg": 1.0,
    "LeftHand": 2.0,
    "RightHand": 2.0,
    "LeftFoot": 2.0,
    "RightFoot": 2.0,
}
