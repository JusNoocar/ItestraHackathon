from typing import Tuple, List, Dict, Any

Coord = Tuple[int, int]

def _manhattan_toroid(a: Coord, b: Coord, size: Tuple[int,int]) -> int:
    dx = abs(a[0]-b[0])
    dy = abs(a[1]-b[1])
    w, h = size
    dx = min(dx, w-dx)
    dy = min(dy, h-dy)
    return dx+dy

def extract_features(next_pos: Coord,
                     head: Coord,
                     stars: List[Coord],
                     apples: List[Coord],
                     opponents: List[Dict[str,Any]],
                     pocket_volume: int,
                     dead_hazard_set: set,
                     star_spawn_points: List[Coord],
                     field_size: Tuple[int,int],
                     current_direction: str,
                     consecutive_same_streak: int
                     ) -> Dict[str, float]:
    f = {}
    f['dead_hazard'] = 1.0 if next_pos in dead_hazard_set else 0.0
    f['star_exists'] = 1.0 if stars else 0.0
    if stars:
        f['dist_to_star'] = min(_manhattan_toroid(next_pos, s, field_size) for s in stars)
        f['star_attack_zone'] = float(min(_manhattan_toroid(next_pos, s, field_size) for s in stars) <= 2)
    else:
        f['dist_to_star'] = 999.0
        f['star_attack_zone'] = 0.0
    # nearest apple
    if apples:
        f['dist_to_apple'] = min(_manhattan_toroid(next_pos, a, field_size) for a in apples)
    else:
        f['dist_to_apple'] = 999.0
    # pocket
    f['pocket'] = float(pocket_volume)
    # opponent distances
    dops = [ _manhattan_toroid(next_pos, op.get('head'), field_size) for op in opponents if op.get('head')]
    f['dist_to_nearest_opponent'] = min(dops) if dops else 999.0
    f['opponent_in_attack_window'] = 1.0 if any(op.get('star_attack_window') for op in opponents) else 0.0
    # spawn proximity
    if star_spawn_points:
        f['dist_to_spawn'] = min(_manhattan_toroid(next_pos, sp, field_size) for sp in star_spawn_points)
    else:
        f['dist_to_spawn'] = 999.0
    f['same_direction'] = 1.0 if current_direction else 0.0
    f['repeat_streak'] = float(consecutive_same_streak)
    # bad apple flag
    f['bad_apple_here'] = 0.0
    return f
