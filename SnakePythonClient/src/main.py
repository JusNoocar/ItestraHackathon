import argparse
import logging
import time
from typing import List, Optional, Tuple

from api import SnakeFieldAPI
from data_structures import Direction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Coord = Tuple[int, int]

_REVERSE_DIRECTIONS = {
    "NORTH": "SOUTH",
    "SOUTH": "NORTH",
    "EAST": "WEST",
    "WEST": "EAST",
}

_DIRECTION_VECTORS = {
    "NORTH": (0, -1),
    "SOUTH": (0, 1),
    "EAST": (1, 0),
    "WEST": (-1, 0),
}


def is_reverse_direction(direction: Direction, current_direction: Direction) -> bool:
    """Return True if `direction` would reverse `current_direction`."""
    return _REVERSE_DIRECTIONS.get(direction) == current_direction


def _manhattan_distance(a: Coord, b: Coord, size: Optional[Tuple[int, int]] = None) -> int:
    """Calculates Manhattan distance, handling wrap-around screen boundaries if size is provided."""
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    if size:
        dx = min(dx, size[0] - dx)
        dy = min(dy, size[1] - dy)
    return dx + dy


def _normalize_coord(value) -> Optional[Coord]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        x, y = value
        if isinstance(x, int) and isinstance(y, int):
            return (x, y)
    if isinstance(value, dict):
        x = value.get("x") if "x" in value else value.get("col")
        y = value.get("y") if "y" in value else value.get("row")
        if isinstance(x, int) and isinstance(y, int):
            return (x, y)
    return None


def compute_direction_toward_nearest_apple(
    head: Coord,
    apples: List[Coord],
    current_direction: Direction,
    other_snakes: List[List[Coord]] = None,
    field_size: Tuple[int, int] = (20, 20),
    my_body: List[Coord] = None,
    winning_snake_head: Optional[Coord] = None,
    attack_mode: bool = False,
) -> Direction:
    """Calculates the best next move based on survival, apple collection,
    defensive apple circling, and targeted kamikaze strikes on a toroidal wrapping grid.
    """
    width, height = field_size
    other_snakes = other_snakes or []
    my_body = my_body or [head]
    my_length = len(my_body)

    # Gather all lethal obstacle zones (snake bodies)
    obstacle_cells = set(my_body)
    opponent_heads = set()
    for snake_body in other_snakes:
        obstacle_cells.update(snake_body)
        if snake_body:
            opponent_heads.add(snake_body[0])

    best_direction = current_direction
    best_score = -float("inf")

    normalized_apples = [apple for apple in (_normalize_coord(item) for item in apples) if apple]

    # Find the dense center of apple clusters using toroidal math
    cluster_center = None
    if normalized_apples:
        best_cluster_count = -1
        for app in normalized_apples:
            count = sum(1 for other in normalized_apples if _manhattan_distance(app, other, field_size) <= 3)
            if count > best_cluster_count:
                best_cluster_count = count
                cluster_center = app

    # Evaluate all 4 physical directions
    for direction, vector in _DIRECTION_VECTORS.items():
        if is_reverse_direction(direction, current_direction):
            continue

        # SCREEN WRAPPING: Apply modulo boundary logic to determine the true next position
        next_pos = ((head[0] + vector[0]) % width, (head[1] + vector[1]) % height)

        # 1. Collision Check (Allow head-on crash ONLY if deliberately executing a winner kill)
        if next_pos in obstacle_cells:
            if attack_mode and next_pos == winning_snake_head:
                pass 
            else:
                continue

        # Base scoring calculation
        score = 0

        # Account for head-collision vulnerabilities on the next turn via wrap-around distance
        for opp_head in opponent_heads:
            if _manhattan_distance(next_pos, opp_head, field_size) == 1:
                if attack_mode and opp_head == winning_snake_head:
                    score += 2000  # Massive encouragement to lock onto target head
                else:
                    score -= 150   # Avoid head-ons with random smaller snakes

        # PHASE 3: Kamikaze Intercept Subroutine
        if attack_mode and winning_snake_head:
            dist_to_winner = _manhattan_distance(next_pos, winning_snake_head, field_size)
            score += (100 - dist_to_winner) * 50
            if next_pos == winning_snake_head:
                score += 100000  # Absolute priority target hit
        else:
            # PHASE 1 & 2: Food Acquisition & Circling
            if normalized_apples:
                closest_apple = min(normalized_apples, key=lambda a: _manhattan_distance(next_pos, a, field_size))
                dist_to_apple = _manhattan_distance(next_pos, closest_apple, field_size)
                score += (100 - dist_to_apple) * 10

                # Check if competitors are crowding our food
                min_opp_dist = min(
                    [_manhattan_distance(closest_apple, cell, field_size) for snake in other_snakes for cell in snake]
                    + [999]
                )
                if min_opp_dist < 5:
                    score -= (5 - min_opp_dist) * 20

                # PHASE 2: Lock-and-Circle Area Protection
                if my_length >= 10 and cluster_center:
                    dist_to_cluster = _manhattan_distance(next_pos, cluster_center, field_size)
                    score += (50 - dist_to_cluster) * 15
                    
                    # Coil matching: Hug your own body segments tightly across boundaries to protect food perimeter
                    adjacent_to_self = sum(1 for cell in my_body[3:] if _manhattan_distance(next_pos, cell, field_size) == 1)
                    score += adjacent_to_self * 35

        # Lookahead verification to ensure we maintain open escape channels around wrapped spaces
        free_neighbors = 0
        for v in _DIRECTION_VECTORS.values():
            nx, ny = (next_pos[0] + v[0]) % width, (next_pos[1] + v[1]) % height
            if (nx, ny) not in obstacle_cells:
                free_neighbors += 1
        score += free_neighbors * 40

        if score > best_score:
            best_score = score
            best_direction = direction

    # Emergency Fallback: If trapped completely, look to drag an opponent head down with us across edges
    if best_score == -float("inf"):
        for direction, vector in _DIRECTION_VECTORS.items():
            if is_reverse_direction(direction, current_direction):
                continue
            next_pos = ((head[0] + vector[0]) % width, (head[1] + vector[1]) % height)
            for snake_body in other_snakes:
                if snake_body and next_pos == snake_body[0]:
                    return direction
        return current_direction

    return best_direction


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

    if not api.set_direction(currentDirection):
        logger.warning("Initial direction registration failed, continuing anyway")

    while alive:
        time.sleep(0.5)  # Avoid rate limiting error
        field = api.get_field()
        if field is None:
            continue

        my_snake = field.snakes.get(team_name)
        if not my_snake or not my_snake.alive:
            alive = False
            break

        head = my_snake.body[0]
        apples = getattr(field, "apples", [])
        
        other_snakes = [
            snake.body
            for snake_name, snake in field.snakes.items()
            if snake_name != team_name and snake.alive
        ]

        # Strategic Evaluation: Locate the leading threat
        winning_snake_head = None
        max_opponent_len = 0
        for snake_name, snake in field.snakes.items():
            if snake_name != team_name and snake.alive:
                if len(snake.body) > max_opponent_len:
                    max_opponent_len = len(snake.body)
                    winning_snake_head = snake.body[0]

        my_length = len(my_snake.body)
        
        # Attack trigger: If an opponent gets significantly larger than us, pivot strategy to elimination
        attack_mode = max_opponent_len > (my_length + 4)

        currentDirection = compute_direction_toward_nearest_apple(
            head=head,
            apples=apples,
            current_direction=currentDirection,
            other_snakes=other_snakes,
            field_size=getattr(field, "size", (20, 20)),
            my_body=my_snake.body,
            winning_snake_head=winning_snake_head,
            attack_mode=attack_mode,
        )
        time.sleep(0.25)  # Avoid rate limiting error
        if not api.set_direction(currentDirection):
            logger.warning("Failed to update direction to %s", currentDirection)