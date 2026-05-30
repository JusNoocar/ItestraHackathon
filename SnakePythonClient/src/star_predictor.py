from typing import List, Tuple, Optional

Coord = Tuple[int, int]

def predict_star(tick_counter: int, star_interval: int, star_spawn_points: List[Coord]) -> Tuple[int, Optional[Coord]]:
    """Return (ticks_until_next_star, preferred_spawn_point).
    If spawn points known, return nearest spawn as target (caller chooses nearest by distance).
    """
    if not star_interval or star_interval <= 0:
        star_interval = 15
    ticks_until = (star_interval - (tick_counter % star_interval)) % star_interval
    target = None
    if star_spawn_points:
        # return the list's first as default; caller can choose nearest
        target = star_spawn_points[0]
    return ticks_until, target
