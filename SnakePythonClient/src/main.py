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
#     """Finds the true, maze-navigated distance to the nearest apple. Returns 999 if completely walled off."""
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

#     return 999  # No valid path exists to any apple in the list


# def compute_direction_toward_nearest_apple(
#     head: Coord,
#     apples: List[Coord],
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

#     # 1. Map all hard obstacles
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

#     # Calculate Phase Mode based on population
#     alive_opponents_count = len(opponent_heads)
#     is_crowded_phase = alive_opponents_count >= 2

#     # Optimistic pocket obstacles (Tail sliding away)
#     pocket_obstacles = set(obstacle_cells)
#     clearance_count = max(1, int(my_length * 0.35))
#     if my_length > 4:
#         for segment in my_body[-clearance_count:]:
#             if segment in pocket_obstacles:
#                 pocket_obstacles.remove(segment)

#     best_direction = current_direction
#     best_score = -float("inf")

#     normalized_apples = [apple for apple in (_normalize_coord(item) for item in apples) if apple]

#     for direction, vector in _DIRECTION_VECTORS.items():
#         if is_reverse_direction(direction, current_direction):
#             continue

#         next_pos = ((head[0] + vector[0]) % width, (head[1] + vector[1]) % height)

#         if next_pos in obstacle_cells:
#             continue

#         score = 0

#         # 1. Pocket Safety (Can we fit?)
#         required_escape_volume = min(8, my_length + 1)
#         pocket_volume = _calculate_pocket_volume(next_pos, pocket_obstacles, width, height, required_escape_volume)
        
#         if pocket_volume < required_escape_volume:
#             score -= 3000 
#         else:
#             score += pocket_volume * 10

#         # 2. Collision / Crowded Phase Avoidance
#         for opp_head in opponent_heads:
#             dist_to_opp = _manhattan_distance(next_pos, opp_head, field_size)
#             if dist_to_opp == 1:
#                 if attack_mode and opp_head == winning_snake_head:
#                     score += 5000  
#                 else:
#                     score -= 4000  
            
#             if is_crowded_phase and dist_to_opp <= 3:
#                 score -= 200  

#         # 3. TRUE PATHFINDING (The Apple Fix)
#         if attack_mode and winning_snake_head:
#             dist_to_winner = _manhattan_distance(next_pos, winning_snake_head, field_size)
#             score += (100 - dist_to_winner) * 100
#             if next_pos == winning_snake_head:
#                 score += 500000
#         else:
#             viable_apples = []
#             for app in normalized_apples:
#                 our_dist = _manhattan_distance(head, app, field_size)
#                 is_contested = False
#                 for opp_head in opponent_heads:
#                     if _manhattan_distance(opp_head, app, field_size) <= our_dist:
#                         is_contested = True
#                         break
#                 if not is_contested:
#                     viable_apples.append(app)

#             target_apples = viable_apples if viable_apples else normalized_apples
            
#             # --- THE BFS UPGRADE ---
#             # Instead of guessing distance, we map the exact maze route.
#             true_distance_to_apple = _bfs_distance_to_nearest_apple(next_pos, target_apples, pocket_obstacles, width, height)
            
#             if true_distance_to_apple != 999:
#                 # We have a mathematically verified, clear path to an apple.
#                 apple_weight = 60 if is_crowded_phase else 150
#                 score += (100 - true_distance_to_apple) * apple_weight  

#                 if not is_crowded_phase:
#                     for opp_head in opponent_heads:
#                         if _manhattan_distance(next_pos, opp_head, field_size) == 2:  
#                             score += 80  
#             else:
#                 # If ALL apples are walled off, maximize open space to survive until they open up
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
#     parser.add_argument("team_name", help="Name of the team/snake")
#     parser.add_argument("game_name", help="Name of the game to join")
#     parser.add_argument("--password", default="test", help="Password for server")
#     parser.add_argument("--base_url", default="http://localhost:3030",
#                         help="Base URL of the game server (default: http://localhost:3030)")
#     args = parser.parse_args()

#     team_name = args.team_name
#     base_url = args.base_url
#     game_name = args.game_name
#     password = args.password

#     alive = True
#     currentDirection: Direction = "NORTH"

#     api = SnakeFieldAPI(base_url, team_name, game_name, password)

#     if not api.set_direction(currentDirection):
#         logger.warning("Initial direction registration failed, continuing anyway")

#     while alive:
#         time.sleep(0.4)  
#         field = api.get_field()
#         if field is None:
#             continue

#         my_snake = field.snakes.get(team_name)
#         if not my_snake or not my_snake.alive:
#             alive = False
#             break

#         head = my_snake.body[0]
#         apples = getattr(field, "apples", [])
        
#         other_snakes = [
#             snake.body
#             for snake_name, snake in field.snakes.items()
#             if snake_name != team_name and snake.alive
#         ]

#         dead_snakes = [
#             snake.body
#             for snake_name, snake in field.snakes.items()
#             if snake_name != team_name and not snake.alive
#         ]

#         winning_snake_head = None
#         max_opponent_len = 0
#         for snake_name, snake in field.snakes.items():
#             if snake_name != team_name and snake.alive:
#                 if len(snake.body) > max_opponent_len:
#                     max_opponent_len = len(snake.body)
#                     winning_snake_head = snake.body[0]

#         my_length = len(my_snake.body)
#         attack_mode = max_opponent_len > (my_length + 5) and max_opponent_len > 15

#         currentDirection = compute_direction_toward_nearest_apple(
#             head=head,
#             apples=apples,
#             current_direction=currentDirection,
#             other_snakes=other_snakes,
#             field_size=getattr(field, "size", (20, 20)),
#             my_body=my_snake.body,
#             winning_snake_head=winning_snake_head,
#             attack_mode=attack_mode,
#             dead_snakes=dead_snakes,
#         )
        
#         if not api.set_direction(currentDirection):
#             logger.warning("Failed to update direction to %s", currentDirection)


'''

dhdzhbzgbgzdhtzdn

'''
import argparse
import logging
import time
import heapq
from typing import List, Optional, Tuple, Set

from api import SnakeFieldAPI
from data_structures import Direction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Coord = Tuple[int, int]

# --- DYNAMIC ENUM DETECTION ---
IS_ENUM = hasattr(Direction, "__members__")

def to_api_direction(dir_str: str) -> Direction:
    if IS_ENUM:
        return Direction[dir_str]
    return dir_str

def to_internal_str(dir_obj) -> str:
    if IS_ENUM and hasattr(dir_obj, "name"):
        return dir_obj.name
    return str(dir_obj).upper()

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

def is_reverse_direction(direction: str, current_direction: str) -> bool:
    return _REVERSE_DIRECTIONS.get(direction) == current_direction

def _manhattan_distance(a: Coord, b: Coord, size: Optional[Tuple[int, int]] = None) -> int:
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    if size:
        dx = min(dx, size[0] - dx)
        dy = min(dy, size[1] - dy)
    return dx + dy

def _infer_current_direction(head: Coord, my_body: List[Coord], width: int, height: int, fallback: str) -> str:
    if len(my_body) < 2:
        return fallback
    neck = my_body[1]
    dx = (head[0] - neck[0]) % width
    if dx > width // 2:
        dx -= width
    dy = (head[1] - neck[1]) % height
    if dy > height // 2:
        dy -= height

    if abs(dx) > abs(dy):
        return "EAST" if dx > 0 else "WEST"
    elif abs(dy) > abs(dx):
        return "SOUTH" if dy > 0 else "NORTH"
    return fallback

def _calculate_dynamic_pocket(
    start_pos: Coord, 
    clear_time: dict, 
    dead_cells: Set[Coord], 
    bad_apple_set: Set[Coord],
    width: int, 
    height: int, 
    max_cells: int
) -> int:
    if start_pos in dead_cells or clear_time.get(start_pos, 0) > 1 or start_pos in bad_apple_set:
        return 0
        
    visited = {start_pos}
    queue = [(start_pos, 1)] 
    head_idx = 0
    
    while head_idx < len(queue):
        curr, d = queue[head_idx]
        head_idx += 1
        
        if len(visited) >= max_cells:
            return len(visited)
            
        for v in _DIRECTION_VECTORS.values():
            nxt = ((curr[0] + v[0]) % width, (curr[1] + v[1]) % height)
            if nxt not in visited and nxt not in bad_apple_set:
                if not (nxt in dead_cells or clear_time.get(nxt, 0) > d + 1):
                    visited.add(nxt)
                    queue.append((nxt, d + 1))
    return len(visited)

def _dijkstra_to_nearest_apple(
    start_pos: Coord,
    target_apples: List[Coord],
    bad_apple_set: Set[Coord],
    clear_time: dict,
    dead_cells: Set[Coord],
    width: int,
    height: int
) -> Tuple[int, int]:
    if not target_apples:
        return 999999, 999
    if start_pos in dead_cells or clear_time.get(start_pos, 0) > 1:
        return 999999, 999

    start_cost = 50000 if start_pos in bad_apple_set else 1
    pq = [(start_cost, 1, start_pos)]
    best_costs = {start_pos: start_cost}
    target_set = set(target_apples)
    
    while pq:
        cost, steps, curr = heapq.heappop(pq)
        
        if cost > best_costs.get(curr, float('inf')):
            continue
            
        if curr in target_set:
            return cost, steps - 1
            
        for v in _DIRECTION_VECTORS.values():
            nxt = ((curr[0] + v[0]) % width, (curr[1] + v[1]) % height)
            arrival_turn = steps + 1
            
            if nxt in dead_cells or clear_time.get(nxt, 0) > arrival_turn:
                continue
                
            next_cost = cost + (50000 if nxt in bad_apple_set else 1)
            if next_cost < best_costs.get(nxt, float('inf')):
                best_costs[nxt] = next_cost
                heapq.heappush(pq, (next_cost, arrival_turn, nxt))
                
    return 999999, 999

def compute_direction_master(
    head: Coord,
    apples: List[Coord],
    bad_apples: List[Coord],
    current_direction_raw,
    other_snakes: List[List[Coord]] = None,
    field_size: Tuple[int, int] = (20, 20),
    my_body: List[Coord] = None,
    winning_snake_head: Optional[Coord] = None,
    attack_mode: bool = False,
    dead_snakes: List[List[Coord]] = None,
) -> str:
    
    width, height = field_size
    other_snakes = other_snakes or []
    dead_snakes = dead_snakes or []
    my_body = my_body or [head]
    my_length = len(my_body)

    current_direction = to_internal_str(current_direction_raw)
    current_direction = _infer_current_direction(head, my_body, width, height, current_direction)

    dead_cells = set()
    for snake_body in dead_snakes:
        for segment in snake_body:
            dead_cells.add(segment)

    volatile_opponents = set()
    for snake_body in other_snakes:
        if not snake_body:
            continue
        opp_head = snake_body[0]
        
        is_at_risk = False
        for other_snake in other_snakes:
            if other_snake and other_snake[0] != opp_head:
                if _manhattan_distance(opp_head, other_snake[0], field_size) <= 2:
                    is_at_risk = True
                    break
        if not is_at_risk and _manhattan_distance(opp_head, head, field_size) <= 2:
            is_at_risk = True
            
        if not is_at_risk:
            for v in _DIRECTION_VECTORS.values():
                adj = ((opp_head[0] + v[0]) % width, (opp_head[1] + v[1]) % height)
                if adj in dead_cells:
                    is_at_risk = True
                    break
                    
        if is_at_risk:
            volatile_opponents.add(opp_head)

    clear_time = {}
    L_my = len(my_body)
    for i, segment in enumerate(my_body):
        t = L_my - i
        if segment not in clear_time or t > clear_time[segment]:
            clear_time[segment] = t
            
    opponent_heads = set()
    opp_head_to_len = {}
    for snake_body in other_snakes:
        if not snake_body:
            continue
        opp_head = snake_body[0]
        opponent_heads.add(opp_head)
        opp_head_to_len[opp_head] = len(snake_body)
        
        L_opp = len(snake_body)
        is_frozen = opp_head in volatile_opponents
        
        for j, segment in enumerate(snake_body):
            if is_frozen:
                dead_cells.add(segment)
            else:
                t = L_opp - j
                if segment not in clear_time or t > clear_time[segment]:
                    clear_time[segment] = t

    bad_apple_set = set(bad_apples)
    alive_opponents_count = len(opponent_heads)
    is_crowded_phase = alive_opponents_count >= 2

    loop_mode = (my_length > 11 or len(bad_apples) >= 40) and not attack_mode
    tail_pos = my_body[-1] if my_length > 1 else head

    best_direction = current_direction
    best_score = -float("inf")

    for direction, vector in _DIRECTION_VECTORS.items():
        if is_reverse_direction(direction, current_direction):
            continue

        next_pos = ((head[0] + vector[0]) % width, (head[1] + vector[1]) % height)

        if next_pos in dead_cells or clear_time.get(next_pos, 0) > 1:
            continue

        score = 0

        if direction == current_direction:
            score += 10  

        max_safety_check = max(my_length + 5, 15)
        pocket_volume = _calculate_dynamic_pocket(next_pos, clear_time, dead_cells, bad_apple_set, width, height, max_safety_check)
        
        if pocket_volume < my_length + 1:
            score -= 2000000000  
            score += pocket_volume * 100000
        else:
            score += pocket_volume * 10000

        if next_pos in bad_apple_set:
            score -= 100000000 
        
        # --- UNIVERSAL PROXIMITY HAZARD FILTER ---
        # Safeguards the snake uniformly, whether in loop defensive mode or aggressive hunting
        for opp_head in opponent_heads:
            dist_to_opp = _manhattan_distance(next_pos, opp_head, field_size)
            opp_len = opp_head_to_len.get(opp_head, 0)
            
            if dist_to_opp == 1:
                # Next tile shares an edge with an enemy head. They can occupy it this turn.
                if my_length > opp_len + 1:
                    if loop_mode:
                        # Even if bigger, avoid running into them head-on while holding a safe tail-loop
                        score -= 200000000
                    else:
                        score += 1000000    # Intentionally bully them if actively in hunting mode
                else:
                    # Absolute danger zone: Severe penalty to prevent unexpected head-on elimination
                    score -= 1500000000

        # --- MODE-SPECIFIC PATH SELECTION ---
        if loop_mode:
            cost, steps = _dijkstra_to_nearest_apple(next_pos, [tail_pos], bad_apple_set, clear_time, dead_cells, width, height)
            if cost < 999999:
                score += (1000 - steps) * 200000
            else:
                dist_to_tail = _manhattan_distance(next_pos, tail_pos, field_size)
                score += (100 - dist_to_tail) * 500
        else:
            # Standard Aggressive Play
            if attack_mode and winning_snake_head:
                dist_to_winner = _manhattan_distance(next_pos, winning_snake_head, field_size)
                score += (1000 - dist_to_winner) * 1000
            else:
                cost, steps = _dijkstra_to_nearest_apple(next_pos, apples, bad_apple_set, clear_time, dead_cells, width, height)
                if cost < 999999:
                    score += (1000 - steps) * (2000 if is_crowded_phase else 4000)
                    score -= cost * 50  
                else:
                    score += pocket_volume * 5

        if score > best_score:
            best_score = score
            best_direction = direction

    if best_score == -float("inf"):
        for direction, vector in _DIRECTION_VECTORS.items():
            if is_reverse_direction(direction, current_direction):
                continue
            next_pos = ((head[0] + vector[0]) % width, (head[1] + vector[1]) % height)
            if next_pos not in dead_cells and clear_time.get(next_pos, 0) <= 1:
                return direction
        return current_direction

    return best_direction

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Snake game bot client")
    parser.add_argument("team_name")
    parser.add_argument("game_name")
    parser.add_argument("--password", default="test")
    parser.add_argument("--base_url", default="http://localhost:3030")
    args = parser.parse_args()

    api = SnakeFieldAPI(args.base_url, args.team_name, args.game_name, args.password)
    alive = True
    currentDirectionStr = "NORTH"

    api.set_direction(to_api_direction(currentDirectionStr))

    while alive:
        time.sleep(0.5)  
        try:
            field = api.get_field()
            if field is None: 
                continue

            my_snake = field.snakes.get(args.team_name)
            if not my_snake or not my_snake.alive: 
                break

            head = my_snake.body[0]
            raw_items = getattr(field, "items", [])
            apples = []
            bad_apples = []

            if isinstance(raw_items, list):
                for entry in raw_items:
                    if isinstance(entry, (list, tuple)) and len(entry) == 2:
                        pos, type_ = entry
                        if isinstance(pos, (list, tuple)) and len(pos) == 2:
                            coord = (int(pos[0]), int(pos[1]))
                            t_str = to_internal_str(type_)
                            if "APPLE" in t_str and "BAD" not in t_str: apples.append(coord)
                            elif "BAD" in t_str: bad_apples.append(coord)
                    elif isinstance(entry, dict):
                        pos = entry.get("position") or entry.get("pos") or entry.get("coords")
                        type_ = entry.get("type") or entry.get("item_type")
                        if isinstance(pos, (list, tuple)) and len(pos) == 2:
                            coord = (int(pos[0]), int(pos[1]))
                            t_str = to_internal_str(type_)
                            if "APPLE" in t_str and "BAD" not in t_str: apples.append(coord)
                            elif "BAD" in t_str: bad_apples.append(coord)
                    else:
                        try:
                            p = getattr(entry, "position", None) or getattr(entry, "pos", None)
                            t = getattr(entry, "type", None) or getattr(entry, "item_type", None)
                            if p and t and len(p) >= 2:
                                coord = (int(p[0]), int(p[1]))
                                t_str = to_internal_str(t)
                                if "APPLE" in t_str and "BAD" not in t_str: apples.append(coord)
                                elif "BAD" in t_str: bad_apples.append(coord)
                        except Exception:
                            pass

            if not apples and hasattr(field, "apples"):
                for a in getattr(field, "apples", []):
                    if isinstance(a, (list, tuple)) and len(a) == 2:
                        apples.append((int(a[0]), int(a[1])))
            if not bad_apples and hasattr(field, "bad_apples"):
                for ba in getattr(field, "bad_apples", []):
                    if isinstance(ba, (list, tuple)) and len(ba) == 2:
                        bad_apples.append((int(ba[0]), int(ba[1])))
            
            other_snakes = [snake.body for name, snake in field.snakes.items() if name != args.team_name and snake.alive]
            dead_snakes = [snake.body for name, snake in field.snakes.items() if name != args.team_name and not snake.alive]

            winning_snake_head = None
            max_opp_len = 0
            for name, snake in field.snakes.items():
                if name != args.team_name and snake.alive and len(snake.body) > max_opp_len:
                    max_opp_len = len(snake.body)
                    winning_snake_head = snake.body[0]

            attack_mode = max_opp_len > (len(my_snake.body) + 3) or max_opp_len > 20

            currentDirectionStr = compute_direction_master(
                head=head,
                apples=apples,
                bad_apples=bad_apples,
                current_direction_raw=currentDirectionStr,
                other_snakes=other_snakes,
                field_size=getattr(field, "size", (20, 20)),
                my_body=my_snake.body,
                winning_snake_head=winning_snake_head,
                attack_mode=attack_mode,
                dead_snakes=dead_snakes
            )
            
            api_ready_dir = to_api_direction(currentDirectionStr)
            if not api.set_direction(api_ready_dir):
                logger.warning(f"Network missed direction update to {currentDirectionStr}")
                
        except Exception as e:
            logger.error(f"Handled runtime frame anomaly: {e}", exc_info=True)