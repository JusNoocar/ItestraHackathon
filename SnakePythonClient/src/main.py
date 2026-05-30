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

    # Clean incoming direction format immediately
    current_direction = to_internal_str(current_direction_raw)
    current_direction = _infer_current_direction(head, my_body, width, height, current_direction)

    dead_cells = set()
    for snake_body in dead_snakes:
        for segment in snake_body:
            dead_cells.add(segment)

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
        for j, segment in enumerate(snake_body):
            t = L_opp - j
            if segment not in clear_time or t > clear_time[segment]:
                clear_time[segment] = t

    bad_apple_set = set(bad_apples)
    alive_opponents_count = len(opponent_heads)
    is_crowded_phase = alive_opponents_count >= 2

    best_direction = current_direction
    best_score = -float("inf")

    for direction, vector in _DIRECTION_VECTORS.items():
        if is_reverse_direction(direction, current_direction):
            continue

        next_pos = ((head[0] + vector[0]) % width, (head[1] + vector[1]) % height)

        if next_pos in dead_cells or clear_time.get(next_pos, 0) > 1:
            continue

        score = 0

        # Gentle tie-breaker momentum
        if direction == current_direction:
            score += 10  

        # Pocket safety checks
        max_safety_check = my_length + 5
        pocket_volume = _calculate_dynamic_pocket(next_pos, clear_time, dead_cells, bad_apple_set, width, height, max_safety_check)
        
        if pocket_volume < min(my_length + 1, 5):
            score -= 500000000  
        else:
            score += pocket_volume * 10
            if pocket_volume < my_length:
                score -= (my_length - pocket_volume) * 100

        if next_pos in bad_apple_set:
            score -= 100000000 
        
        # Combat trapping
        for opp_head in opponent_heads:
            dist_to_opp = _manhattan_distance(next_pos, opp_head, field_size)
            opp_len = opp_head_to_len.get(opp_head, 0)
            
            if dist_to_opp == 1:
                if attack_mode and opp_head == winning_snake_head:
                    score += 100000000  
                elif my_length > opp_len + 1:
                    score += 1000000    
                else:
                    score -= 200000000   

        # High-priority apple attraction 
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

    # Set initial direction properly safely typed
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

            # Format-agnostic item parser
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

            # Alternative parsing properties fallback
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

            attack_mode = max_opp_len > (len(my_snake.body) + 5) and max_opp_len > 15

            # Compute direction (returns internal clean string)
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
            
            # Send command translated to native API format
            api_ready_dir = to_api_direction(currentDirectionStr)
            if not api.set_direction(api_ready_dir):
                logger.warning(f"Network missed direction update to {currentDirectionStr}")
                
        except Exception as e:
            logger.error(f"Handled runtime frame anomaly: {e}", exc_info=True)
```