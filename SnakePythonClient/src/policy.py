from typing import Dict, List, Tuple

Coord = Tuple[int, int]

def score_features(f: Dict[str, float], weights: Dict[str, float]) -> float:
    s = 0.0
    for k, v in f.items():
        w = weights.get(k, 0.0)
        s += w * v
    return s

def default_weights():
    return {
        'dead_hazard': -100000.0,
        'dist_to_star': -300.0,
        'dist_to_apple': -50.0,
        'pocket': 500.0,
        'dist_to_nearest_opponent': 30.0,
        'opponent_in_attack_window': -5000.0,
        'dist_to_spawn': -400.0,
        'same_direction': 5.0,
        'repeat_streak': -200.0,
        'bad_apple_here': -100000.0,
    }
