import argparse
import time
from typing import List, Tuple

from api import SnakeFieldAPI
from data_structures import Direction

Coord = Tuple[int, int]

_REVERSE_DIRECTIONS = {
    "NORTH": "SOUTH",
    "SOUTH": "NORTH",
    "EAST": "WEST",
    "WEST": "EAST",
}


def is_reverse_direction(direction: Direction, current_direction: Direction) -> bool:
    """Return True if `direction` would reverse `current_direction`."""
    return _REVERSE_DIRECTIONS.get(direction) == current_direction


def _manhattan_distance(a: Coord, b: Coord) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _apple_safety_penalty(apple: Coord, other_snakes: List[List[Coord]], safe_distance: int = 5) -> int:
    if not other_snakes:
        return 0

    min_dist = min(
        _manhattan_distance(apple, cell)
        for snake in other_snakes
        for cell in snake
    )

    if min_dist >= safe_distance:
        return 0

    return (safe_distance - min_dist) * 10


def compute_direction_toward_nearest_apple(
    head: Coord,
    apples: List[Coord],
    current_direction: Direction,
    other_snakes: List[List[Coord]] = None,
) -> Direction:
    """Choose a direction toward a good apple target.

    The selected apple is the nearest one with a preference for apples
    that are not too close to other snakes, improving the chance we
    reach it before a competitor.
    """
    if not apples:
        return current_direction

    other_snakes = other_snakes or []

    def apple_cost(apple: Coord) -> int:
        distance = _manhattan_distance(head, apple)
        safety_penalty = _apple_safety_penalty(apple, other_snakes)
        return distance + safety_penalty

    target = min(apples, key=apple_cost)
    dx = target[0] - head[0]
    dy = target[1] - head[1]

    if abs(dx) >= abs(dy):
        primary = "EAST" if dx > 0 else "WEST" if dx < 0 else None
        secondary = "SOUTH" if dy > 0 else "NORTH" if dy < 0 else None
    else:
        primary = "SOUTH" if dy > 0 else "NORTH" if dy < 0 else None
        secondary = "EAST" if dx > 0 else "WEST" if dx < 0 else None

    for direction in (primary, secondary):
        if direction and not is_reverse_direction(direction, current_direction):
            return direction

    return current_direction


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Snake game bot client")
    parser.add_argument("team_name", help="Name of the team/snake")
    parser.add_argument("game_name", help="Name of the game to join")
    parser.add_argument("--password", default="test", help="Password for server")
    parser.add_argument("--base_url", default="http://localhost:3030",
                        help="Base URL of the game server (default: http://localhost:3030)")
    args = parser.parse_args()

    team_name = args.team_name
    base_url = args.base_url
    game_name = args.game_name
    password = args.password

    alive = True
    currentDirection: Direction = "NORTH"

    api = SnakeFieldAPI(base_url, team_name, game_name, password)

    # initial posting to register
    api.set_direction(currentDirection)

    while alive:
        time.sleep(0.5)  # avoid rate limiting error
        field = api.get_field()
        api.set_direction(currentDirection)
