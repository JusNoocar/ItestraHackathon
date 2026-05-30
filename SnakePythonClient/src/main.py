# # import argparse
# # import logging
# # import time
# # from typing import List, Optional, Tuple

# # from api import SnakeFieldAPI
# # from data_structures import Direction

# # logging.basicConfig(level=logging.INFO)
# # logger = logging.getLogger(__name__)

# # Coord = Tuple[int, int]

# # _REVERSE_DIRECTIONS = {
# #     "NORTH": "SOUTH",
# #     "SOUTH": "NORTH",
# #     "EAST": "WEST",
# #     "WEST": "EAST",
# # }

# # _DIRECTION_VECTORS = {
# #     "NORTH": (0, -1),
# #     "SOUTH": (0, 1),
# #     "EAST": (1, 0),
# #     "WEST": (-1, 0),
# # }


# # def is_reverse_direction(direction: Direction, current_direction: Direction) -> bool:
# #     """Return True if `direction` would reverse `current_direction`."""
# #     return _REVERSE_DIRECTIONS.get(direction) == current_direction


# # def _manhattan_distance(a: Coord, b: Coord, size: Optional[Tuple[int, int]] = None) -> int:
# #     """Calculates Manhattan distance, handling wrap-around screen boundaries if size is provided."""
# #     dx = abs(a[0] - b[0])
# #     dy = abs(a[1] - b[1])
# #     if size:
# #         dx = min(dx, size[0] - dx)
# #         dy = min(dy, size[1] - dy)
# #     return dx + dy


# # def _normalize_coord(value) -> Optional[Coord]:
# #     if isinstance(value, (list, tuple)) and len(value) == 2:
# #         x, y = value
# #         if isinstance(x, int) and isinstance(y, int):
# #             return (x, y)
# #     if isinstance(value, dict):
# #         x = value.get("x") if "x" in value else value.get("col")
# #         y = value.get("y") if "y" in value else value.get("row")
# #         if isinstance(x, int) and isinstance(y, int):
# #             return (x, y)
# #     return None


# # def compute_direction_toward_nearest_apple(
# #     head: Coord,
# #     apples: List[Coord],
# #     current_direction: Direction,
# #     other_snakes: List[List[Coord]] = None,
# #     field_size: Tuple[int, int] = (20, 20),
# #     my_body: List[Coord] = None,
# #     winning_snake_head: Optional[Coord] = None,
# #     attack_mode: bool = False,
# # ) -> Direction:
# #     """Calculates the best next move based on survival, apple collection,
# #     defensive apple circling, and targeted kamikaze strikes on a toroidal wrapping grid.
# #     """
# #     width, height = field_size
# #     other_snakes = other_snakes or []
# #     my_body = my_body or [head]
# #     my_length = len(my_body)

# #     # Gather all lethal obstacle zones (snake bodies)
# #     obstacle_cells = set(my_body)
# #     opponent_heads = set()
# #     for snake_body in other_snakes:
# #         obstacle_cells.update(snake_body)
# #         if snake_body:
# #             opponent_heads.add(snake_body[0])

# #     best_direction = current_direction
# #     best_score = -float("inf")

# #     normalized_apples = [apple for apple in (_normalize_coord(item) for item in apples) if apple]

# #     # Find the dense center of apple clusters using toroidal math
# #     cluster_center = None
# #     if normalized_apples:
# #         best_cluster_count = -1
# #         for app in normalized_apples:
# #             count = sum(1 for other in normalized_apples if _manhattan_distance(app, other, field_size) <= 3)
# #             if count > best_cluster_count:
# #                 best_cluster_count = count
# #                 cluster_center = app

# #     # Evaluate all 4 physical directions
# #     for direction, vector in _DIRECTION_VECTORS.items():
# #         if is_reverse_direction(direction, current_direction):
# #             continue

# #         # SCREEN WRAPPING: Apply modulo boundary logic to determine the true next position
# #         next_pos = ((head[0] + vector[0]) % width, (head[1] + vector[1]) % height)

# #         # 1. Collision Check (Allow head-on crash ONLY if deliberately executing a winner kill)
# #         if next_pos in obstacle_cells:
# #             if attack_mode and next_pos == winning_snake_head:
# #                 pass 
# #             else:
# #                 continue

# #         # Base scoring calculation
# #         score = 0

# #         # Account for head-collision vulnerabilities on the next turn via wrap-around distance
# #         for opp_head in opponent_heads:
# #             if _manhattan_distance(next_pos, opp_head, field_size) == 1:
# #                 if attack_mode and opp_head == winning_snake_head:
# #                     score += 2000  # Massive encouragement to lock onto target head
# #                 else:
# #                     score -= 150   # Avoid head-ons with random smaller snakes

# #         # PHASE 3: Kamikaze Intercept Subroutine
# #         if attack_mode and winning_snake_head:
# #             dist_to_winner = _manhattan_distance(next_pos, winning_snake_head, field_size)
# #             score += (100 - dist_to_winner) * 50
# #             if next_pos == winning_snake_head:
# #                 score += 100000  # Absolute priority target hit
# #         else:
# #             # PHASE 1 & 2: Food Acquisition & Circling
# #             if normalized_apples:
# #                 closest_apple = min(normalized_apples, key=lambda a: _manhattan_distance(next_pos, a, field_size))
# #                 dist_to_apple = _manhattan_distance(next_pos, closest_apple, field_size)
# #                 score += (100 - dist_to_apple) * 10

# #                 # Check if competitors are crowding our food
# #                 min_opp_dist = min(
# #                     [_manhattan_distance(closest_apple, cell, field_size) for snake in other_snakes for cell in snake]
# #                     + [999]
# #                 )
# #                 if min_opp_dist < 5:
# #                     score -= (5 - min_opp_dist) * 20

# #                 # PHASE 2: Lock-and-Circle Area Protection
# #                 if my_length >= 10 and cluster_center:
# #                     dist_to_cluster = _manhattan_distance(next_pos, cluster_center, field_size)
# #                     score += (50 - dist_to_cluster) * 15
                    
# #                     # Coil matching: Hug your own body segments tightly across boundaries to protect food perimeter
# #                     adjacent_to_self = sum(1 for cell in my_body[3:] if _manhattan_distance(next_pos, cell, field_size) == 1)
# #                     score += adjacent_to_self * 35

# #         # Lookahead verification to ensure we maintain open escape channels around wrapped spaces
# #         free_neighbors = 0
# #         for v in _DIRECTION_VECTORS.values():
# #             nx, ny = (next_pos[0] + v[0]) % width, (next_pos[1] + v[1]) % height
# #             if (nx, ny) not in obstacle_cells:
# #                 free_neighbors += 1
# #         score += free_neighbors * 40

# #         if score > best_score:
# #             best_score = score
# #             best_direction = direction

# #     # Emergency Fallback: If trapped completely, look to drag an opponent head down with us across edges
# #     if best_score == -float("inf"):
# #         for direction, vector in _DIRECTION_VECTORS.items():
# #             if is_reverse_direction(direction, current_direction):
# #                 continue
# #             next_pos = ((head[0] + vector[0]) % width, (head[1] + vector[1]) % height)
# #             for snake_body in other_snakes:
# #                 if snake_body and next_pos == snake_body[0]:
# #                     return direction
# #         return current_direction

# #     return best_direction


# # if __name__ == "__main__":
# #     parser = argparse.ArgumentParser(description="Snake game bot client")
# #     parser.add_argument("team_name", help="Name of the team/snake")
# #     parser.add_argument("game_name", help="Name of the game to join")
# #     parser.add_argument("--password", default="test", help="Password for server")
# #     parser.add_argument("--base_url", default="http://localhost:3030",
# #                         help="Base URL of the game server (default: http://localhost:3030)")
# #     args = parser.parse_args()

# #     team_name = args.team_name
# #     base_url = args.base_url
# #     game_name = args.game_name
# #     password = args.password

# #     alive = True
# #     currentDirection: Direction = "NORTH"

# #     api = SnakeFieldAPI(base_url, team_name, game_name, password)

# #     if not api.set_direction(currentDirection):
# #         logger.warning("Initial direction registration failed, continuing anyway")

# #     while alive:
# #         time.sleep(0.5)  # Avoid rate limiting error
# #         field = api.get_field()
# #         if field is None:
# #             continue

# #         my_snake = field.snakes.get(team_name)
# #         if not my_snake or not my_snake.alive:
# #             alive = False
# #             break

# #         head = my_snake.body[0]
# #         apples = getattr(field, "apples", [])
        
# #         other_snakes = [
# #             snake.body
# #             for snake_name, snake in field.snakes.items()
# #             if snake_name != team_name and snake.alive
# #         ]

# #         # Strategic Evaluation: Locate the leading threat
# #         winning_snake_head = None
# #         max_opponent_len = 0
# #         for snake_name, snake in field.snakes.items():
# #             if snake_name != team_name and snake.alive:
# #                 if len(snake.body) > max_opponent_len:
# #                     max_opponent_len = len(snake.body)
# #                     winning_snake_head = snake.body[0]

# #         my_length = len(my_snake.body)
        
# #         # Attack trigger: If an opponent gets significantly larger than us, pivot strategy to elimination
# #         attack_mode = max_opponent_len > (my_length + 4)

# #         currentDirection = compute_direction_toward_nearest_apple(
# #             head=head,
# #             apples=apples,
# #             current_direction=currentDirection,
# #             other_snakes=other_snakes,
# #             field_size=getattr(field, "size", (20, 20)),
# #             my_body=my_snake.body,
# #             winning_snake_head=winning_snake_head,
# #             attack_mode=attack_mode,
# #         )
# #         time.sleep(0.25)  # Avoid rate limiting error
# #         if not api.set_direction(currentDirection):
# #             logger.warning("Failed to update direction to %s", currentDirection)





import argparse
import logging
import time
from typing import List, Optional, Tuple, Set

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
    return _REVERSE_DIRECTIONS.get(direction) == current_direction


def _manhattan_distance(a: Coord, b: Coord, size: Optional[Tuple[int, int]] = None) -> int:
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


def _calculate_pocket_volume(start_pos: Coord, obstacle_cells: Set[Coord], width: int, height: int, max_cells_needed: int) -> int:
    if start_pos in obstacle_cells:
        return 0
    visited = {start_pos}
    queue = [start_pos]
    head_idx = 0
    while head_idx < len(queue):
        curr = queue[head_idx]
        head_idx += 1
        if len(visited) >= max_cells_needed:
            return len(visited)
        for v in _DIRECTION_VECTORS.values():
            nxt = ((curr[0] + v[0]) % width, (curr[1] + v[1]) % height)
            if nxt not in obstacle_cells and nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)
    return len(visited)


def _bfs_distance_to_nearest_apple(start_pos: Coord, target_apples: List[Coord], obstacle_cells: Set[Coord], width: int, height: int) -> int:
    """Finds the true, maze-navigated distance to the nearest apple. Returns 999 if completely walled off."""
    if not target_apples:
        return 999
    if start_pos in target_apples:
        return 0

    visited = {start_pos}
    queue = [(start_pos, 0)]
    target_set = set(target_apples)
    head_idx = 0

    while head_idx < len(queue):
        curr, dist = queue[head_idx]
        head_idx += 1

        if curr in target_set:
            return dist

        for v in _DIRECTION_VECTORS.values():
            nxt = ((curr[0] + v[0]) % width, (curr[1] + v[1]) % height)
            if nxt not in obstacle_cells and nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, dist + 1))

    return 999  # No valid path exists to any apple in the list


def compute_direction_toward_nearest_apple(
    head: Coord,
    apples: List[Coord],
    current_direction: Direction,
    other_snakes: List[List[Coord]] = None,
    field_size: Tuple[int, int] = (20, 20),
    my_body: List[Coord] = None,
    winning_snake_head: Optional[Coord] = None,
    attack_mode: bool = False,
    dead_snakes: List[List[Coord]] = None,
) -> Direction:
    
    width, height = field_size
    other_snakes = other_snakes or []
    dead_snakes = dead_snakes or []
    my_body = my_body or [head]
    my_length = len(my_body)

    # 1. Map all hard obstacles
    obstacle_cells = set()
    for segment in my_body[:-1]:
        obstacle_cells.add(segment)
        
    opponent_heads = set()
    for snake_body in other_snakes:
        if not snake_body:
            continue
        opponent_heads.add(snake_body[0])
        for segment in snake_body[:-1]:
            obstacle_cells.add(segment)

    for snake_body in dead_snakes:
        if not snake_body:
            continue
        for segment in snake_body:
            obstacle_cells.add(segment)

    # Calculate Phase Mode based on population
    alive_opponents_count = len(opponent_heads)
    is_crowded_phase = alive_opponents_count >= 2

    # Optimistic pocket obstacles (Tail sliding away)
    pocket_obstacles = set(obstacle_cells)
    clearance_count = max(1, int(my_length * 0.35))
    if my_length > 4:
        for segment in my_body[-clearance_count:]:
            if segment in pocket_obstacles:
                pocket_obstacles.remove(segment)

    best_direction = current_direction
    best_score = -float("inf")

    normalized_apples = [apple for apple in (_normalize_coord(item) for item in apples) if apple]

    for direction, vector in _DIRECTION_VECTORS.items():
        if is_reverse_direction(direction, current_direction):
            continue

        next_pos = ((head[0] + vector[0]) % width, (head[1] + vector[1]) % height)

        if next_pos in obstacle_cells:
            continue

        score = 0

        # 1. Pocket Safety (Can we fit?)
        required_escape_volume = min(8, my_length + 1)
        pocket_volume = _calculate_pocket_volume(next_pos, pocket_obstacles, width, height, required_escape_volume)
        
        if pocket_volume < required_escape_volume:
            score -= 3000 
        else:
            score += pocket_volume * 10

        # 2. Collision / Crowded Phase Avoidance
        for opp_head in opponent_heads:
            dist_to_opp = _manhattan_distance(next_pos, opp_head, field_size)
            if dist_to_opp == 1:
                if attack_mode and opp_head == winning_snake_head:
                    score += 5000  
                else:
                    score -= 4000  
            
            if is_crowded_phase and dist_to_opp <= 3:
                score -= 200  

        # 3. TRUE PATHFINDING (The Apple Fix)
        if attack_mode and winning_snake_head:
            dist_to_winner = _manhattan_distance(next_pos, winning_snake_head, field_size)
            score += (100 - dist_to_winner) * 100
            if next_pos == winning_snake_head:
                score += 500000
        else:
            viable_apples = []
            for app in normalized_apples:
                our_dist = _manhattan_distance(head, app, field_size)
                is_contested = False
                for opp_head in opponent_heads:
                    if _manhattan_distance(opp_head, app, field_size) <= our_dist:
                        is_contested = True
                        break
                if not is_contested:
                    viable_apples.append(app)

            target_apples = viable_apples if viable_apples else normalized_apples
            
            # --- THE BFS UPGRADE ---
            # Instead of guessing distance, we map the exact maze route.
            true_distance_to_apple = _bfs_distance_to_nearest_apple(next_pos, target_apples, pocket_obstacles, width, height)
            
            if true_distance_to_apple != 999:
                # We have a mathematically verified, clear path to an apple.
                apple_weight = 60 if is_crowded_phase else 150
                score += (100 - true_distance_to_apple) * apple_weight  

                if not is_crowded_phase:
                    for opp_head in opponent_heads:
                        if _manhattan_distance(next_pos, opp_head, field_size) == 2:  
                            score += 80  
            else:
                # If ALL apples are walled off, maximize open space to survive until they open up
                score += pocket_volume * 50

        if score > best_score:
            best_score = score
            best_direction = direction

    # Emergency Fallback
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
        time.sleep(0.4)  
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

        dead_snakes = [
            snake.body
            for snake_name, snake in field.snakes.items()
            if snake_name != team_name and not snake.alive
        ]

        winning_snake_head = None
        max_opponent_len = 0
        for snake_name, snake in field.snakes.items():
            if snake_name != team_name and snake.alive:
                if len(snake.body) > max_opponent_len:
                    max_opponent_len = len(snake.body)
                    winning_snake_head = snake.body[0]

        my_length = len(my_snake.body)
        attack_mode = max_opponent_len > (my_length + 5) and max_opponent_len > 15

        currentDirection = compute_direction_toward_nearest_apple(
            head=head,
            apples=apples,
            current_direction=currentDirection,
            other_snakes=other_snakes,
            field_size=getattr(field, "size", (20, 20)),
            my_body=my_snake.body,
            winning_snake_head=winning_snake_head,
            attack_mode=attack_mode,
            dead_snakes=dead_snakes,
        )
        
        if not api.set_direction(currentDirection):
            logger.warning("Failed to update direction to %s", currentDirection)


'''

dhdzhbzgbgzdhtzdn

'''
# import argparse
# import logging
# import time
# from typing import List, Optional, Tuple, Set

# from api import SnakeFieldAPI
# from data_structures import Direction

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# Coord = Tuple[int, int]

# _REVERSE_DIRECTIONS = {
#     "NORTH": "SOUTH",
#     "SOUTH": "NORTH",
#     "EAST": "WEST",
#     "WEST": "EAST",
# }

# _DIRECTION_VECTORS = {
#     "NORTH": (0, -1),
#     "SOUTH": (0, 1),
#     "EAST": (1, 0),
#     "WEST": (-1, 0),
# }

# def is_reverse_direction(direction: Direction, current_direction: Direction) -> bool:
#     return _REVERSE_DIRECTIONS.get(direction) == current_direction

# def _manhattan_distance(a: Coord, b: Coord, size: Optional[Tuple[int, int]] = None) -> int:
#     dx = abs(a[0] - b[0])
#     dy = abs(a[1] - b[1])
#     if size:
#         dx = min(dx, size[0] - dx)
#         dy = min(dy, size[1] - dy)
#     return dx + dy

# def _normalize_coord(value) -> Optional[Coord]:
#     if isinstance(value, (list, tuple)) and len(value) == 2:
#         x, y = value
#         if isinstance(x, int) and isinstance(y, int):
#             return (x, y)
#     if isinstance(value, dict):
#         x = value.get("x") if "x" in value else value.get("col")
#         y = value.get("y") if "y" in value else value.get("row")
#         if isinstance(x, int) and isinstance(y, int):
#             return (x, y)
#     return None

# def _calculate_pocket_volume(start_pos: Coord, obstacle_cells: Set[Coord], width: int, height: int, max_cells_needed: int) -> int:
#     if start_pos in obstacle_cells:
#         return 0
#     visited = {start_pos}
#     queue = [start_pos]
#     head_idx = 0
#     while head_idx < len(queue):
#         curr = queue[head_idx]
#         head_idx += 1
#         if len(visited) >= max_cells_needed:
#             return len(visited)
#         for v in _DIRECTION_VECTORS.values():
#             nxt = ((curr[0] + v[0]) % width, (curr[1] + v[1]) % height)
#             if nxt not in obstacle_cells and nxt not in visited:
#                 visited.add(nxt)
#                 queue.append(nxt)
#     return len(visited)

# def _bfs_distance_to_nearest_apple(start_pos: Coord, target_apples: List[Coord], obstacle_cells: Set[Coord], width: int, height: int) -> int:
#     if not target_apples:
#         return 999
#     if start_pos in target_apples:
#         return 0
#     visited = {start_pos}
#     queue = [(start_pos, 0)]
#     target_set = set(target_apples)
#     head_idx = 0
#     while head_idx < len(queue):
#         curr, dist = queue[head_idx]
#         head_idx += 1
#         if curr in target_set:
#             return dist
#         for v in _DIRECTION_VECTORS.values():
#             nxt = ((curr[0] + v[0]) % width, (curr[1] + v[1]) % height)
#             if nxt not in obstacle_cells and nxt not in visited:
#                 visited.add(nxt)
#                 queue.append((nxt, dist + 1))
#     return 999

# def compute_direction_master(
#     head: Coord,
#     apples: List[Coord],
#     bad_apples: List[Coord],
#     current_direction: Direction,
#     other_snakes: List[List[Coord]] = None,
#     field_size: Tuple[int, int] = (20, 20),
#     my_body: List[Coord] = None,
#     winning_snake_head: Optional[Coord] = None,
#     attack_mode: bool = False,
#     dead_snakes: List[List[Coord]] = None,
# ) -> Direction:
    
#     width, height = field_size
#     other_snakes = other_snakes or []
#     dead_snakes = dead_snakes or []
#     my_body = my_body or [head]
#     my_length = len(my_body)

#     # 1. Map Obstacles
#     obstacle_cells = set()
#     for segment in my_body[:-1]:
#         obstacle_cells.add(segment)
        
#     opponent_heads = set()
#     for snake_body in other_snakes:
#         if not snake_body:
#             continue
#         opponent_heads.add(snake_body[0])
#         for segment in snake_body[:-1]:
#             obstacle_cells.add(segment)

#     for snake_body in dead_snakes:
#         if not snake_body:
#             continue
#         for segment in snake_body:
#             obstacle_cells.add(segment)

#     bad_apple_set = set(bad_apples)
    
#     # Phase Detection
#     alive_opponents_count = len(opponent_heads)
#     is_crowded_phase = alive_opponents_count >= 2

#     # Optimistic pocket obstacles
#     pocket_obstacles = set(obstacle_cells)
#     clearance_count = max(1, int(my_length * 0.35))
#     if my_length > 4:
#         for segment in my_body[-clearance_count:]:
#             if segment in pocket_obstacles:
#                 pocket_obstacles.remove(segment)

#     best_direction = current_direction
#     best_score = -float("inf")

#     for direction, vector in _DIRECTION_VECTORS.items():
#         if is_reverse_direction(direction, current_direction):
#             continue

#         next_pos = ((head[0] + vector[0]) % width, (head[1] + vector[1]) % height)

#         if next_pos in obstacle_cells:
#             continue

#         score = 0

#         # --- BAD APPLE HAZARD ---
#         if next_pos in bad_apple_set:
#             score -= 800  # Soft penalty: eat if necessary, avoid if possible
        
#         # --- POCKET SAFETY (Floodfill) ---
#         required_escape_volume = min(8, my_length + 1)
#         pocket_volume = _calculate_pocket_volume(next_pos, pocket_obstacles, width, height, required_escape_volume)
        
#         if pocket_volume < required_escape_volume:
#             score -= 3000 # Hard penalty: Death trap
#         else:
#             score += pocket_volume * 10

#         # --- BLOCKING & HERDING ---
#         for opp_head in opponent_heads:
#             dist_to_opp = _manhattan_distance(next_pos, opp_head, field_size)
            
#             # Suicide Prevention
#             if dist_to_opp == 1:
#                 if attack_mode and opp_head == winning_snake_head:
#                     score += 5000  
#                 else:
#                     score -= 4000  
            
#             # Herding: Push opponents into BadApples
#             for ba in bad_apples:
#                 if _manhattan_distance(opp_head, ba, field_size) <= 2 and dist_to_opp == 2:
#                     score += 200 # Encourage blocking them into hazards

#             # Crowded Phase Avoidance
#             if is_crowded_phase and dist_to_opp <= 3:
#                 score -= 200

#         # --- TRUE BFS PATHFINDING ---
#         if attack_mode and winning_snake_head:
#             dist_to_winner = _manhattan_distance(next_pos, winning_snake_head, field_size)
#             score += (100 - dist_to_winner) * 100
#         else:
#             true_dist = _bfs_distance_to_nearest_apple(next_pos, apples, pocket_obstacles, width, height)
#             if true_dist != 999:
#                 score += (100 - true_dist) * (60 if is_crowded_phase else 150)
#             else:
#                 score += pocket_volume * 50

#         if score > best_score:
#             best_score = score
#             best_direction = direction

#     # Emergency Fallback
#     if best_score == -float("inf"):
#         for direction, vector in _DIRECTION_VECTORS.items():
#             if is_reverse_direction(direction, current_direction):
#                 continue
#             next_pos = ((head[0] + vector[0]) % width, (head[1] + vector[1]) % height)
#             for snake_body in other_snakes:
#                 if snake_body and next_pos == snake_body[0]:
#                     return direction
#         return current_direction

#     return best_direction

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="Snake game bot client")
#     parser.add_argument("team_name")
#     parser.add_argument("game_name")
#     parser.add_argument("--password", default="test")
#     parser.add_argument("--base_url", default="http://localhost:3030")
#     args = parser.parse_args()

#     api = SnakeFieldAPI(args.base_url, args.team_name, args.game_name, args.password)
#     alive = True
#     currentDirection = "NORTH"

#     # api.set_direction(currentDirection)

#     while alive:
#         time.sleep(0.5)  
#         field = api.get_field()
#         if field is None: continue

#         my_snake = field.snakes.get(args.team_name)
#         if not my_snake or not my_snake.alive: break

#         head = my_snake.body[0]
        
#         # Parsing Items
#         raw_items = getattr(field, "items", [])
#         apples = []
#         bad_apples = []
#         for pos, type_ in raw_items:
#             if type_ == 'Apple': apples.append(tuple(pos))
#             elif type_ == 'BadApple': bad_apples.append(tuple(pos))

#         # print("check ok")
        
#         other_snakes = [snake.body for name, snake in field.snakes.items() if name != args.team_name and snake.alive]
#         dead_snakes = [snake.body for name, snake in field.snakes.items() if name != args.team_name and not snake.alive]

#         winning_snake_head = None
#         max_opp_len = 0
#         for name, snake in field.snakes.items():
#             if name != args.team_name and snake.alive and len(snake.body) > max_opp_len:
#                 max_opp_len = len(snake.body)
#                 winning_snake_head = snake.body[0]

#         attack_mode = max_opp_len > (len(my_snake.body) + 5) and max_opp_len > 15

#         currentDirection = compute_direction_master(
#             head=head,
#             apples=apples,
#             bad_apples=bad_apples,
#             current_direction=currentDirection,
#             other_snakes=other_snakes,
#             field_size=getattr(field, "size", (20, 20)),
#             my_body=my_snake.body,
#             winning_snake_head=winning_snake_head,
#             attack_mode=attack_mode,
#             dead_snakes=dead_snakes
#         )
        
#         if not api.set_direction(currentDirection):
#             logger.warning("Failed to update direction")