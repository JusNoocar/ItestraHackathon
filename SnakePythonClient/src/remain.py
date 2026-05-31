import argparse
import logging
import time
import threading
import json
from typing import List, Optional, Tuple, Set, Dict

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

class LowLatencyGameBuffer:
    def __init__(self):
        self.field = None
        self.lock = threading.Lock()

game_buffer = LowLatencyGameBuffer()

def network_receiver_pipeline(api: SnakeFieldAPI, buffer: LowLatencyGameBuffer, stop_event: threading.Event):
    while not stop_event.is_set():
        try:
            f = api.get_field()
            if f is not None:
                with buffer.lock:
                    buffer.field = f
        except Exception:
            pass
        time.sleep(0.005) # Hyper-fast 5ms network sampling for 12-player matches


class DeepLinearAgent:
    """RL Inference engine tracking weights customized for high-density item configurations."""
    def __init__(self, alpha: float = 0.05, gamma: float = 0.95, weights_path: str = "dqn_12player_weights.json"):
        self.alpha = alpha
        self.gamma = gamma
        self.weights_path = weights_path
        
        self.weights = {
            "lethal_slice_risk": -30.0,      # Prioritize threat evasion
            "poison_density": -20.0,         # Strongly avoid BadApples
            "voronoi_territory": 5.0,        # Secure open spaces
            "instant_stack_proximity": 6.0,  # Grab stacks for evasion/cleanup
            "upgrade_proximity": 4.0,        # Hunt swords and speed boosts
            "exit_redundancy": 3.0,          # Maintain escape options
            "is_stacked_bonus": 10.0         # Highly value safety loops
        }
        self.load_weights()

    def load_weights(self):
        try:
            with open(self.weights_path, "r") as f:
                self.weights.update(json.load(f))
        except Exception:
            pass

    def save_weights(self):
        try:
            with open(self.weights_path, "w") as f:
                json.dump(self.weights, f, indent=4)
        except Exception:
            pass

    def evaluate_features(self, features: Dict[str, float]) -> float:
        return sum(self.weights.get(k, 0.0) * v for k, v in features.items())

    def learn_step(self, prev_features: Dict[str, float], reward: float, max_next_q: float):
        old_q = self.evaluate_features(prev_features)
        td_error = (reward + self.gamma * max_next_q) - old_q
        
        for k, v in prev_features.items():
            if k in self.weights:
                self.weights[k] += self.alpha * td_error * v
        self.save_weights()


def is_reverse_direction(direction: Direction, current_direction: Direction) -> bool:
    return _REVERSE_DIRECTIONS.get(direction) == current_direction

def _normalize_coord(value) -> Optional[Coord]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return (int(value[0]), int(value[1]))
    if isinstance(value, dict):
        x = value.get("x", value.get("col"))
        y = value.get("y", value.get("row"))
        if x is not None and y is not None:
            return (int(x), int(y))
    return None

def _compute_voronoi_territory(my_next_head: Coord, other_snakes: List[List[Coord]], obstacle_cells: Set[Coord], width: int, height: int) -> float:
    if my_next_head in obstacle_cells:
        return 0.0

    opp_dist: Dict[Coord, int] = {}
    opp_queue = []
    
    for snake in other_snakes:
        if not snake: continue
        opp_head = snake[0]
        for v in _DIRECTION_VECTORS.values():
            nxt = ((opp_head[0] + v[0]) % width, (opp_head[1] + v[1]) % height)
            if nxt not in obstacle_cells:
                opp_queue.append((nxt, 1))
                opp_dist[nxt] = 1

    head_idx = 0
    while head_idx < len(opp_queue):
        curr, d = opp_queue[head_idx]
        head_idx += 1
        for v in _DIRECTION_VECTORS.values():
            nxt = ((curr[0] + v[0]) % width, (curr[1] + v[1]) % height)
            if nxt not in obstacle_cells and nxt not in opp_dist:
                opp_dist[nxt] = d + 1
                opp_queue.append((nxt, d + 1))

    my_dist = {my_next_head: 0}
    my_queue = [(my_next_head, 0)]
    my_head_idx = 0
    
    while my_head_idx < len(my_queue):
        curr, d = my_queue[my_head_idx]
        my_head_idx += 1
        for v in _DIRECTION_VECTORS.values():
            nxt = ((curr[0] + v[0]) % width, (curr[1] + v[1]) % height)
            if nxt not in obstacle_cells and nxt not in my_dist:
                my_dist[nxt] = d + 1
                my_queue.append((nxt, d + 1))

    my_territory = 0
    for cell, d in my_dist.items():
        if cell not in opp_dist or d < opp_dist[cell]:
            my_territory += 1

    return float(my_territory) / max(1, (width * height))

def _bfs_distance_to_targets(start_pos: Coord, targets: List[Coord], obstacle_cells: Set[Coord], width: int, height: int) -> int:
    if not targets: return 999
    if start_pos in targets: return 0

    visited = {start_pos}
    queue = [(start_pos, 0)]
    target_set = set(targets)
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
    return 999


def process_tactical_step(
    head: Coord,
    current_direction: Direction,
    field_size: Tuple[int, int],
    my_body: List[Coord],
    other_snakes: List[List[Coord]],
    dead_snakes: List[List[Coord]],
    stacks: List[Coord],
    upgrades: List[Coord],
    bad_apples: List[Coord],
    agent: DeepLinearAgent
) -> Tuple[Direction, Dict[str, float]]:
    width, height = field_size
    
    # Accurate state processing for overlapping body configurations
    unique_my_nodes = set(my_body)
    is_fully_stacked = len(unique_my_nodes) == 1

    obstacle_cells = set()
    if not is_fully_stacked:
        for seg in my_body[:-1]:
            if seg != head:
                obstacle_cells.add(seg)
                
    for s in other_snakes:
        if s:
            opp_head = s[0]
            # Account for other bots being stacked at spawn coordinates
            if len(set(s)) > 1:
                for seg in s[:-1]:
                    if seg != opp_head:
                        obstacle_cells.add(seg)

    for ds in dead_snakes:
        if ds: obstacle_cells.update(ds)

    # Danger tracking: Calculate proximity threat from all 11 competing heads
    danger_zones = set()
    for s in other_snakes:
        if not s: continue
        opp_h = s[0]
        danger_zones.add(opp_h)
        for v in _DIRECTION_VECTORS.values():
            danger_zones.add(((opp_h[0] + v[0]) % width, (opp_h[1] + v[1]) % height))

    best_direction = current_direction
    best_q_val = -float("inf")
    chosen_features = {}

    for direction, vector in _DIRECTION_VECTORS.items():
        if is_reverse_direction(direction, current_direction):
            continue

        next_pos = ((head[0] + vector[0]) % width, (head[1] + vector[1]) % height)
        if next_pos in obstacle_cells:
            continue

        features = {
            "lethal_slice_risk": 1.0 if (next_pos in danger_zones and not is_fully_stacked) else 0.0,
            "poison_density": 1.0 if next_pos in bad_apples else 0.0,
            "voronoi_territory": _compute_voronoi_territory(next_pos, other_snakes, obstacle_cells, width, height),
            "instant_stack_proximity": 0.0,
            "upgrade_proximity": 0.0,
            "exit_redundancy": 0.0,
            "is_stacked_bonus": 1.0 if is_fully_stacked else 0.0
        }

        if stacks:
            d_stack = _bfs_distance_to_targets(next_pos, stacks, obstacle_cells, width, height)
            features["instant_stack_proximity"] = 1.0 / (d_stack + 1)
            
        if upgrades:
            d_up = _bfs_distance_to_targets(next_pos, upgrades, obstacle_cells, width, height)
            features["upgrade_proximity"] = 1.0 / (d_up + 1)

        free_exits = 0
        for v in _DIRECTION_VECTORS.values():
            neigh = ((next_pos[0] + v[0]) % width, (next_pos[1] + v[1]) % height)
            if neigh not in obstacle_cells: free_exits += 1
        features["exit_redundancy"] = free_exits / 4.0

        q_value = agent.evaluate_features(features)

        if q_value > best_q_val:
            best_q_val = q_value
            best_direction = direction
            chosen_features = features

    if best_q_val == -float("inf"):
        for direction, vector in _DIRECTION_VECTORS.items():
            if is_reverse_direction(direction, current_direction): continue
            next_pos = ((head[0] + vector[0]) % width, (head[1] + vector[1]) % height)
            if next_pos not in obstacle_cells:
                return direction
        return current_direction

    return best_direction, chosen_features


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="12-Player Grand Arena Combat Bot")
    parser.add_argument("team_name", help="Snake identifier string")
    parser.add_argument("game_name", help="Match lobby identifier")
    parser.add_argument("--password", default="test")
    parser.add_argument("--base_url", default="http://localhost:3030")
    args = parser.parse_args()

    agent = DeepLinearAgent()
    api = SnakeFieldAPI(args.base_url, args.team_name, args.game_name, args.password)
    
    currentDirection: Direction = "NORTH"
    api.set_direction(currentDirection)

    stop_event = threading.Event()
    receiver_thread = threading.Thread(
        target=network_receiver_pipeline, 
        args=(api, game_buffer, stop_event), 
        daemon=True
    )
    receiver_thread.start()

    alive = True
    prev_features = None
    prev_length = None

    try:
        while alive:
            time.sleep(0.012) # Faster computation cycle to keep up with multi-snake actions
            
            field = None
            with game_buffer.lock:
                field = game_buffer.field
            if field is None:
                continue

            my_snake = field.snakes.get(args.team_name)
            if not my_snake or not my_snake.alive:
                alive = False
                break

            head = my_snake.body[0]
            width, height = getattr(field, "size", (41, 41))
            current_length = len(my_snake.body)

            stacks = []
            upgrades = []
            bad_apples = []
            raw_items = getattr(field, "items", None)
            
            if raw_items is not None:
                for item in raw_items:
                    pos, kind = (item[0], item[1]) if isinstance(item, (list, tuple)) else (item.get("pos"), item.get("type"))
                    normalized = _normalize_coord(pos)
                    if normalized:
                        if kind == "InstantStack":
                            stacks.append(normalized)
                        elif kind in ["Sword", "Speedboost", "Apple", "Star"]:
                            upgrades.append(normalized)
                        elif kind == "BadApple":
                            bad_apples.append(normalized)

            other_snakes = [s.body for name, s in field.snakes.items() if name != args.team_name and s.alive]
            dead_snakes = [s.body for name, s in field.snakes.items() if name != args.team_name and not s.alive]

            next_direction, current_features = process_tactical_step(
                head=head,
                current_direction=currentDirection,
                field_size=(width, height),
                my_body=my_snake.body,
                other_snakes=other_snakes,
                dead_snakes=dead_snakes,
                stacks=stacks,
                upgrades=upgrades,
                bad_apples=bad_apples,
                agent=agent
            )

            # High-Dimensional Spatial Learning Feedback Loop
            if prev_features is not None and prev_length is not None:
                reward = 0.1
                if current_length < prev_length:
                    reward -= 75.0  # High penalty for tail contraction
                if len(set(my_snake.body)) == 1:
                    reward += 25.0  # Reward safe stacked states

                max_next_q = agent.evaluate_features(current_features)
                agent.learn_step(prev_features, reward, max_next_q)

            prev_features = current_features
            prev_length = current_length

            if next_direction in ("NORTH", "SOUTH", "EAST", "WEST"):
                currentDirection = next_direction
                api.set_direction(currentDirection)

    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        receiver_thread.join(timeout=1.0)