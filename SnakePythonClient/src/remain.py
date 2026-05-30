
import argparse
import logging
import time
from typing import List, Optional, Tuple, Set

from api import SnakeFieldAPI
from data_structures import Direction
from rl_agent import RLAgent
from policy import default_weights
from features import extract_features

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


def _find_apple_clusters(apples: List[Coord], field_size: Tuple[int, int], cluster_radius: int = 4) -> List[List[Coord]]:
    """Group nearby apples into clusters and return clusters sorted by density."""
    if not apples:
        return []
    
    width, height = field_size
    visited = set()
    clusters = []
    
    for apple in apples:
        if apple in visited:
            continue
        cluster = []
        queue = [apple]
        visited.add(apple)
        
        head_idx = 0
        while head_idx < len(queue):
            curr = queue[head_idx]
            head_idx += 1
            cluster.append(curr)
            
            for other in apples:
                if other not in visited and _manhattan_distance(curr, other, field_size) <= cluster_radius:
                    visited.add(other)
                    queue.append(other)
        
        clusters.append(cluster)
    
    # Sort by cluster density (size is proxy for density in small areas)
    clusters.sort(key=lambda c: len(c), reverse=True)
    return clusters


def _find_safe_corridors(head: Coord, apples: List[Coord], bad_apples: List[Coord], 
                        field_size: Tuple[int, int], obstacle_cells: Set[Coord]) -> List[Coord]:
    """Find paths to good apples that avoid bad apple concentrations."""
    if not apples:
        return []
    
    width, height = field_size
    bad_apple_set = set(bad_apples)
    safe_paths = []
    
    for apple in apples:
        # Count bad apples within 2 cells of this apple
        bad_nearby = sum(1 for bad in bad_apples if _manhattan_distance(apple, bad, field_size) <= 2)
        
        # Only consider apples with 2 or fewer bad apples nearby
        if bad_nearby <= 2:
            safe_paths.append((apple, bad_nearby))
    
    # Sort by safety (fewer bad apples nearby)
    safe_paths.sort(key=lambda x: x[1])
    return [apple for apple, _ in safe_paths]


def _can_trap_opponent(my_head: Coord, opp_head: Coord, bad_apples: List[Coord], 
                       field_size: Tuple[int, int], my_length: int, opp_length: int) -> bool:
    """Check if we can potentially drive an opponent into a bad apple trap."""
    if my_length <= opp_length:
        return False
    
    dist = _manhattan_distance(my_head, opp_head, field_size)
    bad_nearby = sum(1 for bad in bad_apples if _manhattan_distance(opp_head, bad, field_size) <= 3)
    
    # Can trap if close and opponent is surrounded by bad apples
    return dist <= 4 and bad_nearby >= 3


def _count_bad_apple_density(pos: Coord, bad_apples: List[Coord], field_size: Tuple[int, int], radius: int = 3) -> int:
    """Count how many bad apples are near a position."""
    return sum(1 for bad in bad_apples if _manhattan_distance(pos, bad, field_size) <= radius)


def _find_safe_zone(head: Coord, field_size: Tuple[int, int], obstacle_cells: Set[Coord], 
                    bad_apples: List[Coord], search_radius: int = 6) -> Optional[Coord]:
    """Find the safest zone in the field with minimum bad apple density."""
    width, height = field_size
    best_zone = None
    best_safety = float('inf')
    
    # Sample several positions in expanding search
    for dx in range(-search_radius, search_radius + 1):
        for dy in range(-search_radius, search_radius + 1):
            if dx == 0 and dy == 0:
                continue
            
            test_pos = ((head[0] + dx) % width, (head[1] + dy) % height)
            if test_pos in obstacle_cells:
                continue
            
            bad_density = _count_bad_apple_density(test_pos, bad_apples, field_size, radius=2)
            if bad_density < best_safety:
                best_safety = bad_density
                best_zone = test_pos
    
    return best_zone if best_safety < float('inf') else None


def _can_catch_snake_head(my_head: Coord, my_length: int, opp_head: Coord, opp_length: int, 
                          field_size: Tuple[int, int], obstacle_cells: Set[Coord]) -> bool:
    """Check if we can potentially catch the opponent head in a collision."""
    width, height = field_size
    if my_length >= opp_length:
        return _manhattan_distance(my_head, opp_head, field_size) <= 3
    return False


def _predict_next_danger_zones(other_snakes: List[List[Coord]], field_size: Tuple[int, int]) -> Set[Coord]:
    """Predict where opponent heads will likely move."""
    danger_zones = set()
    width, height = field_size
    
    for snake in other_snakes:
        if not snake:
            continue
        head = snake[0]
        danger_zones.add(head)

        if len(snake) > 1:
            prev_head = snake[1]
            dx = head[0] - prev_head[0]
            dy = head[1] - prev_head[1]
            if dx == width - 1:
                dx = -1
            elif dx == -(width - 1):
                dx = 1
            if dy == height - 1:
                dy = -1
            elif dy == -(height - 1):
                dy = 1
            reverse_vec = (dx, dy)
            for v in _DIRECTION_VECTORS.values():
                if v == reverse_vec:
                    continue
                neighbor = ((head[0] + v[0]) % width, (head[1] + v[1]) % height)
                danger_zones.add(neighbor)
        else:
            for v in _DIRECTION_VECTORS.values():
                neighbor = ((head[0] + v[0]) % width, (head[1] + v[1]) % height)
                danger_zones.add(neighbor)
    
    return danger_zones


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
    bad_apples: List[Coord] = None,
) -> Direction:
    """Enhanced AI for high bad apple spawn rate environment."""
    width, height = field_size
    other_snakes = other_snakes or []
    dead_snakes = dead_snakes or []
    bad_apples = bad_apples or []
    my_body = my_body or [head]
    my_length = len(my_body)

    obstacle_cells = set(my_body[:-1])
    opponent_heads = []
    opponent_snakes_info = []
    
    for snake_body in other_snakes:
        if not snake_body:
            continue
        opp_head = snake_body[0]
        opponent_heads.append(opp_head)
        opponent_snakes_info.append((opp_head, len(snake_body)))
        obstacle_cells.update(snake_body[:-1])

    for snake_body in dead_snakes:
        if not snake_body:
            continue
        obstacle_cells.update(snake_body)

    bad_apple_set = set(_normalize_coord(item) for item in bad_apples if _normalize_coord(item))
    pocket_obstacles = set(obstacle_cells)
    if my_length > 4:
        clearance_count = max(1, int(my_length * 0.35))
        for segment in my_body[-clearance_count:]:
            pocket_obstacles.discard(segment)

    normalized_apples = [apple for apple in (_normalize_coord(item) for item in apples) if apple]
    
    # HIGH BAD APPLE HANDLING: Find safe corridors to good apples
    safe_apples = _find_safe_corridors(head, normalized_apples, bad_apples, field_size, obstacle_cells)
    if not safe_apples:
        safe_apples = normalized_apples  # Fallback to all apples if no safe ones exist
    
    # Find apple clusters for strategic positioning
    apple_clusters = _find_apple_clusters(safe_apples, field_size, cluster_radius=5)
    cluster_centers = [
        tuple(int(sum(c[i] for c in cluster) / len(cluster)) for i in range(2))
        for cluster in apple_clusters
    ] if apple_clusters else []
    
    # Calculate bad apple density at current position
    current_bad_density = _count_bad_apple_density(head, bad_apples, field_size, radius=3)
    
    # Check if we're surrounded by bad apples (emergency situation)
    is_surrounded_by_poison = current_bad_density >= 4

    best_direction = current_direction
    best_score = -float("inf")
    danger_zones = _predict_next_danger_zones(other_snakes, field_size)

    for direction, vector in _DIRECTION_VECTORS.items():
        if is_reverse_direction(direction, current_direction):
            continue

        next_pos = ((head[0] + vector[0]) % width, (head[1] + vector[1]) % height)
        if next_pos in obstacle_cells or next_pos in bad_apple_set:
            continue

        score = 0
        
        # Calculate bad apple threat at this position
        bad_density_next = _count_bad_apple_density(next_pos, bad_apples, field_size, radius=3)
        closest_bad = min([_manhattan_distance(next_pos, bad, field_size) for bad in bad_apple_set] + [999])

        # CRITICAL: Dramatically avoid bad apples when they're high spawn rate
        # Penalty scales with proximity and local density
        if closest_bad <= 1:
            score -= 800  # Direct adjacency is DEATH
        elif closest_bad == 2:
            score -= 400  # Very close is dangerous
        elif closest_bad == 3:
            score -= 150  # Still risky
        
        # Penalize moving toward high bad apple density zones
        if bad_density_next >= 4:
            score -= 500  # Avoid poison zones
        elif bad_density_next >= 2:
            score -= 200

        # CRITICAL: Prioritize eating safe apples (highest weight)
        safe_obstacles = pocket_obstacles.union(bad_apple_set)
        dist_to_safe = _bfs_distance_to_nearest_apple(next_pos, safe_apples, safe_obstacles, width, height)
        
        if dist_to_safe != 999:
            # Boost score dramatically for safe apple access
            safe_apple_score = 5000 - dist_to_safe * 300
            score += safe_apple_score
            
            # Additional bonus for moving toward high-density safe clusters
            if cluster_centers:
                closest_cluster = min(cluster_centers, key=lambda c: _manhattan_distance(next_pos, c, field_size))
                dist_to_cluster = _manhattan_distance(next_pos, closest_cluster, field_size)
                score += (120 - dist_to_cluster) * 12
        else:
            # When no safe apples accessible, find escape corridor
            if cluster_centers:
                closest_cluster = min(cluster_centers, key=lambda c: _manhattan_distance(next_pos, c, field_size))
                dist_to_cluster = _manhattan_distance(next_pos, closest_cluster, field_size)
                score += (120 - dist_to_cluster) * 30
            
            # If surrounded by poison, maximize escape space
            if is_surrounded_by_poison:
                pocket_score = _calculate_pocket_volume(next_pos, pocket_obstacles.union(bad_apple_set), width, height, min(10, my_length + 3))
                score += pocket_score * 150

        # SURVIVAL: Maximize escape routes (crucial with bad apples everywhere)
        free_neighbors = 0
        for v in _DIRECTION_VECTORS.values():
            neighbor = ((next_pos[0] + v[0]) % width, (next_pos[1] + v[1]) % height)
            if neighbor not in obstacle_cells and neighbor not in bad_apple_set:
                free_neighbors += 1
        score += free_neighbors * 120

        # Avoid self-collision
        adjacent_self = sum(
            1
            for cell in my_body[2:]
            if _manhattan_distance(next_pos, cell, field_size) == 1
        )
        score -= adjacent_self * 150

        # OFFENSE: Hunt weaker snakes - TRAP them in bad apple zones and avoid dangerous heads
        head_collision_risk = False
        for opp_head, opp_len in opponent_snakes_info:
            dist_to_opp = _manhattan_distance(next_pos, opp_head, field_size)
            opp_bad_density = _count_bad_apple_density(opp_head, bad_apples, field_size, radius=3)

            if next_pos == opp_head:
                if my_length > opp_len:
                    score += 1600
                else:
                    score -= 1400
                    head_collision_risk = True

            if dist_to_opp == 1:
                if my_length <= opp_len:
                    score -= 650
                elif my_length >= opp_len + 2:
                    score += 250
            elif dist_to_opp == 2:
                if my_length <= opp_len:
                    score -= 250
                elif my_length >= opp_len + 1:
                    score += 120

            # If opponent is in poison zone and we're approaching, encourage the trap
            if opp_bad_density >= 3 and my_length >= opp_len:
                if dist_to_opp <= 4:
                    score += 650  # Drive them further into poison
                elif dist_to_opp <= 8:
                    score += 250

            # Standard hunting logic when we're clearly larger
            if my_length >= opp_len + 2:
                if dist_to_opp <= 2:
                    score += 500 * (my_length - opp_len)
                elif dist_to_opp <= 6:
                    score += (8 - dist_to_opp) * 120
            elif my_length >= opp_len:
                if dist_to_opp <= 1:
                    score += 180
            elif my_length >= opp_len - 3:
                if dist_to_opp <= 3:
                    score += 120
            else:
                if dist_to_opp <= 2:
                    score -= 700  # Avoid bigger snakes more aggressively
                elif dist_to_opp <= 5:
                    score -= (6 - dist_to_opp) * 120

        if head_collision_risk:
            score -= 500

        # EVASION: Avoid danger zones from larger snakes
        if next_pos in danger_zones:
            larger_snakes = [opp_head for opp_head, opp_len in opponent_snakes_info if opp_len >= my_length]
            if larger_snakes:
                score -= 450

        if score > best_score:
            best_score = score
            best_direction = direction

    if best_score == -float("inf"):
        # Emergency fallback: find any safe direction (not near bad apples)
        for direction, vector in _DIRECTION_VECTORS.items():
            if is_reverse_direction(direction, current_direction):
                continue
            next_pos = ((head[0] + vector[0]) % width, (head[1] + vector[1]) % height)
            if next_pos not in obstacle_cells and next_pos not in bad_apple_set:
                closest_bad_fallback = min([_manhattan_distance(next_pos, bad, field_size) for bad in bad_apple_set] + [999])
                if closest_bad_fallback >= 2:  # Only return if at least 2 cells away from poison
                    return direction
        
        # Last resort: return to current direction
        return current_direction

    return best_direction

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Snake game bot client")
    parser.add_argument("team_name", help="Name of the team/snake")
    parser.add_argument("game_name", help="Name of the game to join")
    parser.add_argument("--password", default="test", help="Password for server")
    parser.add_argument("--base_url", default="http://localhost:3030",
                        help="Base URL of the game server (default: http://localhost:3030)")
    parser.add_argument("--enable-rl", action="store_true", help="Enable online RL learning (REINFORCE) during matches")
    parser.add_argument("--rl-learning-rate", type=float, default=1e-4, help="RL online learning rate")
    parser.add_argument("--rl-save-file", type=str, default="rl_weights.json", help="Path to save RL weights")
    args = parser.parse_args()

    team_name = args.team_name
    base_url = args.base_url
    game_name = args.game_name
    password = args.password

    # RL agent optional
    agent = None
    if args.enable_rl:
        feature_keys = list(default_weights().keys())
        agent = RLAgent(feature_keys, lr=args.rl_learning_rate, save_path=args.rl_save_file)

    alive = True
    currentDirection: Direction = "NORTH"
    move_count = 0
    recalc_interval = 1  # Recalculate strategy every move
    # RL bookkeeping
    last_candidate_features = None
    last_action_idx = None
    prev_my_length = None
    prev_num_opponents = None
    consecutive_same_streak = 0
    last_direction = currentDirection

    api = SnakeFieldAPI(base_url, team_name, game_name, password)

    if not api.set_direction(currentDirection):
        logger.warning("Initial direction registration failed, continuing anyway")

    while alive:
        # FAST REFLEXES: Ultra-responsive to bad apple threats
        time.sleep(0.30)
        field = api.get_field()
        if field is None:
            continue

        my_snake = field.snakes.get(team_name)
        if not my_snake or not my_snake.alive:
            alive = False
            break

        head = my_snake.body[0]
        apples = getattr(field, "apples", []) or []
        bad_apples = getattr(field, "bad_apples", []) or []

        # Log bad apple spawn rate to monitor environment
        bad_apple_ratio = len(bad_apples) / max(1, len(bad_apples) + len(apples))

        # Some servers expose item tuples as raw items, so parse them if present.
        raw_items = getattr(field, "items", None)
        if raw_items is not None:
            apples = []
            bad_apples = []
            for item in raw_items:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    pos, kind = item
                    if isinstance(pos, (list, tuple)) and len(pos) == 2:
                        coord = tuple(pos)
                        if kind == "BadApple":
                            bad_apples.append(coord)
                        elif kind == "Apple":
                            apples.append(coord)
                        else:
                            apples.append(coord)
                elif isinstance(item, dict):
                    pos = item.get("position") or item.get("pos") or item.get("coord")
                    kind = item.get("type") or item.get("kind")
                    if isinstance(pos, (list, tuple)) and len(pos) == 2:
                        coord = tuple(pos)
                        if kind == "BadApple":
                            bad_apples.append(coord)
                        elif kind == "Apple":
                            apples.append(coord)
                        else:
                            apples.append(coord)

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

        # Find largest opponent for strategic decisions
        winning_snake_head = None
        max_opponent_len = 0
        num_opponents = len(other_snakes)
        
        for snake_name, snake in field.snakes.items():
            if snake_name != team_name and snake.alive:
                if len(snake.body) > max_opponent_len:
                    max_opponent_len = len(snake.body)
                    winning_snake_head = snake.body[0]

        my_length = len(my_snake.body)
        
        # ADAPTIVE: In high bad apple environment, be more conservative with hunting
        # Focus on survival and eating when poison spawn is high
        if bad_apple_ratio > 0.65:
            # Mainly focus on eating safe apples and surviving
            attack_mode = my_length > max_opponent_len + 5 and num_opponents > 0
        else:
            # More aggressive attack mode when poison ratio is lower
            attack_mode = max_opponent_len > (my_length + 3) and max_opponent_len > 12 and num_opponents > 0
        
        # Override: if we're significantly larger, always be offensive
        if my_length > max_opponent_len + 4:
            attack_mode = True

        move_count += 1
        # If RL is enabled, perform per-tick update from last action and select new action via policy
        if args.enable_rl:
            # compute reward for previous action (if any) using observed state changes
            if last_action_idx is not None and prev_my_length is not None and prev_num_opponents is not None and agent is not None:
                reward = 0.0
                # growth indicates apple eaten or kill
                if len(my_snake.body) > prev_my_length:
                    reward += (len(my_snake.body) - prev_my_length) * 10.0
                # opponent died
                if len(other_snakes) < prev_num_opponents:
                    reward += (prev_num_opponents - len(other_snakes)) * 50.0
                # small living bonus to encourage survival
                reward += 0.1
                try:
                    agent.update_step(last_candidate_features, last_action_idx, reward)
                except Exception:
                    pass

            # build candidate features for 4 possible moves
            width, height = getattr(field, "size", (20, 20))
            obstacle_cells = set(my_snake.body[:-1])
            for s in other_snakes:
                obstacle_cells.update(s[:-1])
            for ds in dead_snakes:
                obstacle_cells.update(ds)
            dead_hazard_set = set(cell for ds in dead_snakes for cell in ds)

            candidate_features = []
            directions_order = ["NORTH", "EAST", "SOUTH", "WEST"]
            for d in directions_order:
                if is_reverse_direction(d, currentDirection):
                    # still include the feature but mark as very low pocket
                    candidate_features.append({})
                    continue
                v = _DIRECTION_VECTORS[d]
                next_pos = ((head[0] + v[0]) % width, (head[1] + v[1]) % height)
                pocket = _calculate_pocket_volume(next_pos, obstacle_cells, width, height, min(30, len(my_snake.body) + 5))
                opp_info = [{"head": s[0], "len": len(s)} for s in other_snakes if s]
                f = extract_features(next_pos, head, [], apples, opp_info, pocket, dead_hazard_set, [], (width, height), currentDirection, consecutive_same_streak)
                # explicit bad apple flag
                f['bad_apple_here'] = 1.0 if next_pos in set(bad_apples) else 0.0
                candidate_features.append(f)

            # choose action via agent
            if agent is not None:
                try:
                    act_idx = agent.select_action(candidate_features, deterministic=False)
                    chosen_dir = directions_order[act_idx]
                    currentDirection = chosen_dir
                    last_candidate_features = candidate_features
                    last_action_idx = act_idx
                except Exception:
                    # fallback to heuristic
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
                        bad_apples=bad_apples,
                    )
            else:
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
                    bad_apples=bad_apples,
                )
            # store previous state snapshot for next-tick reward calculation
            prev_my_length = len(my_snake.body)
            prev_num_opponents = len(other_snakes)
        else:
            if move_count % recalc_interval == 0:
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
                    bad_apples=bad_apples,
                )

        if currentDirection not in ("NORTH", "SOUTH", "EAST", "WEST"):
            logger.warning("Computed invalid direction %s, forcing fallback NORTH", currentDirection)
            currentDirection = "NORTH"

        # Update repeat-streak bookkeeping for feature extractor
        if currentDirection == last_direction:
            consecutive_same_streak += 1
        else:
            consecutive_same_streak = 0
        last_direction = currentDirection

        if not api.set_direction(currentDirection):
            logger.warning("Failed to update direction to %s", currentDirection)

