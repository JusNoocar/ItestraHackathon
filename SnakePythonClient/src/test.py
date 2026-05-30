import argparse
import random
import time
from collections import deque
from typing import Dict, List, Optional, Set, Tuple

import requests

from api import SnakeFieldAPI
from data_structures import Direction, Coord
from Field import Field


DIRECTION_DELTAS: Dict[Direction, Coord] = {
    "NORTH": (0, -1),
    "SOUTH": (0, 1),
    "EAST": (1, 0),
    "WEST": (-1, 0),
}

OPPOSITE: Dict[Direction, Direction] = {
    "NORTH": "SOUTH",
    "SOUTH": "NORTH",
    "EAST": "WEST",
    "WEST": "EAST",
}

ALL_DIRECTIONS: List[Direction] = ["NORTH", "SOUTH", "EAST", "WEST"]

CENTER: Coord = (20, 20)
CENTER_BAD_APPLE: Coord = (20, 20)
CENTER_RUSH_RADIUS = 14


# ============================================================
# SAFE SERVER CALLS
# ============================================================

def safe_get_field(api: SnakeFieldAPI) -> Optional[Field]:
    url = f"{api.base_url}/games/{api.game_name}/state"

    try:
        response = api.session.get(url, timeout=api.timeout)
    except requests.exceptions.RequestException as error:
        print(f"GET connection error: {error}")
        return None

    if response.status_code == 429:
        print("GET 429 rate limited")
        return None

    if response.status_code == 403:
        print("GET 403 forbidden: wrong team/password/game")
        raise SystemExit

    if response.status_code != 200:
        print(f"GET failed: {response.status_code} {response.text}")
        return None

    try:
        data = response.json()
    except ValueError:
        print(f"GET invalid JSON: {response.text}")
        return None

    if "size" not in data:
        print(f"Invalid field response: {data}")
        return None

    return Field.from_dict(data)


def safe_set_direction(api: SnakeFieldAPI, direction: Direction) -> bool:
    url = f"{api.base_url}/games/{api.game_name}/snake/direction"
    payload = {"direction": direction}

    try:
        response = api.session.post(url, json=payload, timeout=api.timeout)
    except requests.exceptions.RequestException as error:
        print(f"POST connection error: {error}")
        return False

    if response.status_code == 429:
        print("POST 429 rate limited")
        return False

    if response.status_code == 403:
        print("POST 403 forbidden: wrong team/password/game")
        raise SystemExit

    if response.status_code != 200:
        print(f"POST failed: {response.status_code} {response.text}")
        return False

    return True


# ============================================================
# BOARD HELPERS
# ============================================================

def wrapped_move(pos: Coord, direction: Direction, size: Coord) -> Coord:
    width, height = size
    dx, dy = DIRECTION_DELTAS[direction]
    return ((pos[0] + dx) % width, (pos[1] + dy) % height)


def wrapped_distance(a: Coord, b: Coord, size: Coord) -> int:
    width, height = size

    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])

    dx = min(dx, width - dx)
    dy = min(dy, height - dy)

    return dx + dy


def direction_from_to(start: Coord, nxt: Coord, size: Coord) -> Optional[Direction]:
    for direction in ALL_DIRECTIONS:
        if wrapped_move(start, direction, size) == nxt:
            return direction
    return None


def all_snake_body_cells(field: Field) -> Set[Coord]:
    occupied: Set[Coord] = set()

    # Dead snakes are obstacles too.
    for snake in field.snakes.values():
        occupied.update(snake.body)

    return occupied


def get_items(field: Field) -> Tuple[List[Coord], List[Coord]]:
    good_apples: List[Coord] = []
    bad_apples: List[Coord] = []

    for item in getattr(field, "items", []):
        if item.kind == "Apple":
            good_apples.append(item.coord)
        elif item.kind == "BadApple":
            bad_apples.append(item.coord)

    # Config-specific safety: center is known bad apple.
    if CENTER_BAD_APPLE not in bad_apples:
        bad_apples.append(CENTER_BAD_APPLE)

    return good_apples, bad_apples


def get_enemy_heads(field: Field, team_name: str) -> List[Coord]:
    heads: List[Coord] = []

    for enemy_team, snake in field.snakes.items():
        if enemy_team == team_name:
            continue

        if snake.alive and snake.body:
            heads.append(snake.body[0])

    return heads


def get_enemy_head_danger(field: Field, team_name: str) -> Set[Coord]:
    danger: Set[Coord] = set()

    for enemy_head in get_enemy_heads(field, team_name):
        for direction in ALL_DIRECTIONS:
            danger.add(wrapped_move(enemy_head, direction, field.size))

    return danger


def count_open_neighbors(pos: Coord, size: Coord, blocked: Set[Coord]) -> int:
    count = 0

    for direction in ALL_DIRECTIONS:
        nxt = wrapped_move(pos, direction, size)

        if nxt not in blocked:
            count += 1

    return count


def flood_fill_space(
    start: Coord,
    size: Coord,
    blocked: Set[Coord],
    limit: int = 900,
) -> int:
    if start in blocked:
        return 0

    queue = deque([start])
    visited = {start}

    while queue and len(visited) < limit:
        current = queue.popleft()

        for direction in ALL_DIRECTIONS:
            nxt = wrapped_move(current, direction, size)

            if nxt in visited:
                continue

            if nxt in blocked:
                continue

            visited.add(nxt)
            queue.append(nxt)

    return len(visited)


def bfs_path_to_target(
    start: Coord,
    target: Coord,
    size: Coord,
    blocked: Set[Coord],
) -> Optional[List[Coord]]:
    if start == target:
        return []

    queue = deque([(start, [])])
    visited = {start}

    while queue:
        current, path = queue.popleft()

        for direction in ALL_DIRECTIONS:
            nxt = wrapped_move(current, direction, size)

            if nxt in visited:
                continue

            if nxt in blocked and nxt != target:
                continue

            new_path = path + [nxt]

            if nxt == target:
                return new_path

            visited.add(nxt)
            queue.append((nxt, new_path))

    return None


def nearest_path_distance(
    start: Coord,
    targets: List[Coord],
    size: Coord,
    blocked: Set[Coord],
) -> Optional[int]:
    if not targets:
        return None

    target_set = set(targets)

    if start in target_set:
        return 0

    queue = deque([(start, 0)])
    visited = {start}

    while queue:
        current, distance = queue.popleft()

        for direction in ALL_DIRECTIONS:
            nxt = wrapped_move(current, direction, size)

            if nxt in visited:
                continue

            if nxt in blocked and nxt not in target_set:
                continue

            if nxt in target_set:
                return distance + 1

            visited.add(nxt)
            queue.append((nxt, distance + 1))

    return None


def is_center_cluster_apple(apple: Coord, size: Coord) -> bool:
    return wrapped_distance(apple, CENTER, size) <= CENTER_RUSH_RADIUS


def own_body_zone(field: Field, team_name: str) -> Set[Coord]:
    snake = field.snakes[team_name]
    zone: Set[Coord] = set()

    for body_part in snake.body[1:]:
        zone.add(body_part)
        for direction in ALL_DIRECTIONS:
            zone.add(wrapped_move(body_part, direction, field.size))

    return zone


def enemy_proximity_penalty(pos: Coord, field: Field, team_name: str) -> float:
    penalty = 0.0

    for enemy_head in get_enemy_heads(field, team_name):
        distance = wrapped_distance(pos, enemy_head, field.size)

        if distance == 0:
            penalty += 2000.0
        elif distance == 1:
            penalty += 700.0
        elif distance == 2:
            penalty += 220.0
        elif distance == 3:
            penalty += 70.0

    return penalty


def center_pull_score(pos: Coord, field: Field) -> float:
    distance = wrapped_distance(pos, CENTER, field.size)

    # Strongly pull inward while outside the apple zone.
    if distance > 13:
        return -distance * 22.0

    # Inside the center area, don't stand exactly on center.
    if pos == CENTER_BAD_APPLE:
        return -10000.0

    # Prefer orbiting around center, not sitting on center.
    if distance <= 2:
        return -120.0

    return max(0.0, 12.0 - distance) * 18.0


# ============================================================
# MOVE SCORING
# ============================================================

def safe_move_score(
    field: Field,
    team_name: str,
    direction: Direction,
    current_direction: Direction,
) -> Optional[float]:
    snake = field.snakes[team_name]
    head = snake.body[0]
    length = len(snake.body)

    if length > 1 and direction == OPPOSITE[current_direction]:
        return None

    good_apples, bad_apples = get_items(field)
    occupied = all_snake_body_cells(field)
    enemy_danger = get_enemy_head_danger(field, team_name)
    body_zone = own_body_zone(field, team_name)

    next_head = wrapped_move(head, direction, field.size)

    # Hard rules.
    if next_head in occupied:
        return None

    if next_head == CENTER_BAD_APPLE:
        return None

    if next_head in bad_apples:
        return None

    future_blocked = set(occupied)
    future_blocked.add(next_head)

    # Bad apples are not passable for planning.
    future_blocked_with_bad = set(future_blocked)
    future_blocked_with_bad.update(bad_apples)

    space = flood_fill_space(
        start=next_head,
        size=field.size,
        blocked=future_blocked_with_bad,
        limit=900,
    )

    exits = count_open_neighbors(
        pos=next_head,
        size=field.size,
        blocked=future_blocked_with_bad,
    )

    center_apples = [
        apple for apple in good_apples
        if is_center_cluster_apple(apple, field.size)
    ]

    good_dist = nearest_path_distance(
        start=next_head,
        targets=center_apples or good_apples,
        size=field.size,
        blocked=future_blocked_with_bad,
    )

    score = 0.0

    # Large map: enough space is good; no need to over-optimize after 500.
    score += min(space, 500) * 3.8

    # Exits matter a lot to avoid corridors.
    score += exits * 95.0

    if exits <= 1:
        score -= 1600.0
    elif exits == 2:
        score -= 180.0

    # Center rush.
    score += center_pull_score(next_head, field)

    # Apple reward.
    if next_head in good_apples:
        center_bonus = 0.0
        if is_center_cluster_apple(next_head, field.size):
            center_bonus = 600.0

        if length <= 12:
            score += 1250.0 + center_bonus
        elif length <= 25:
            score += 850.0 + center_bonus
        else:
            score += 450.0 + center_bonus

    if good_dist is not None:
        if length <= 12:
            score += 1000.0 / (good_dist + 1)
        elif length <= 25:
            score += 650.0 / (good_dist + 1)
        else:
            score += 280.0 / (good_dist + 1)

    # Enemy danger.
    if next_head in enemy_danger:
        score -= 850.0

    score -= enemy_proximity_penalty(next_head, field, team_name)

    # Avoid own body/tail hugging, but not so hard that we avoid center apples.
    if next_head in body_zone:
        score -= 320.0

    if length >= 3:
        tail = snake.body[-1]
        tail_distance = wrapped_distance(next_head, tail, field.size)

        if tail_distance <= 1:
            score -= 850.0
        elif tail_distance == 2:
            score -= 240.0
        elif tail_distance == 3:
            score -= 70.0

    # Avoid tiny spaces.
    if space < length + 8:
        score -= 2200.0

    # Prefer not to jitter.
    if direction == current_direction:
        score += 12.0

    score += random.uniform(0.0, 0.4)

    return score


def choose_center_apple_direction(
    field: Field,
    team_name: str,
    current_direction: Direction,
) -> Optional[Direction]:
    snake = field.snakes[team_name]
    head = snake.body[0]
    length = len(snake.body)

    good_apples, bad_apples = get_items(field)

    if not good_apples:
        return None

    occupied = all_snake_body_cells(field)
    enemy_danger = get_enemy_head_danger(field, team_name)

    center_apples = [
        apple for apple in good_apples
        if is_center_cluster_apple(apple, field.size)
    ]

    targets = center_apples if center_apples else good_apples

    # Hard-block bodies and bad apples.
    path_blocked = set(occupied)
    path_blocked.update(bad_apples)
    path_blocked.add(CENTER_BAD_APPLE)

    candidates: List[Tuple[float, Direction, Coord, int]] = []

    for apple in targets:
        path = bfs_path_to_target(
            start=head,
            target=apple,
            size=field.size,
            blocked=path_blocked,
        )

        if not path:
            continue

        first_step = path[0]
        direction = direction_from_to(head, first_step, field.size)

        if direction is None:
            continue

        if length > 1 and direction == OPPOSITE[current_direction]:
            continue

        next_head = wrapped_move(head, direction, field.size)

        if next_head in enemy_danger:
            continue

        move_score = safe_move_score(
            field=field,
            team_name=team_name,
            direction=direction,
            current_direction=current_direction,
        )

        if move_score is None:
            continue

        distance = len(path)
        apple_center_distance = wrapped_distance(apple, CENTER, field.size)

        score = move_score

        # Aggressive center-apple pathing.
        score += 4200.0 / (distance + 1)

        # Prefer center cluster apples strongly.
        if is_center_cluster_apple(apple, field.size):
            score += 900.0

        # Prefer apples close to center, but never center bad apple.
        score += max(0.0, 15.0 - apple_center_distance) * 90.0

        # Very close apple = take it.
        if distance <= 2:
            score += 900.0
        elif distance <= 5:
            score += 400.0

        if next_head == apple:
            score += 2200.0

        # Do not chase absurdly far targets forever.
        if distance > 24:
            score -= (distance - 24) * 35.0

        candidates.append((score, direction, apple, distance))

    if not candidates:
        return None

    candidates.sort(reverse=True, key=lambda item: item[0])
    score, direction, apple, distance = candidates[0]

    print(
        f"CENTER APPLE MODE | Move={direction} | Apple={apple} | "
        f"Dist={distance} | Score={score:.1f} | Len={length} | "
        f"Apples={len(good_apples)}"
    )

    return direction


def choose_direction(
    field: Field,
    team_name: str,
    current_direction: Direction,
) -> Direction:
    if team_name not in field.snakes:
        return current_direction

    snake = field.snakes[team_name]

    if not snake.alive or not snake.body:
        return current_direction

    # First priority: center apple cluster.
    apple_direction = choose_center_apple_direction(
        field=field,
        team_name=team_name,
        current_direction=current_direction,
    )

    if apple_direction is not None:
        return apple_direction

    # Second priority: survival + moving inward.
    scored_moves: List[Tuple[float, Direction]] = []

    for direction in ALL_DIRECTIONS:
        score = safe_move_score(
            field=field,
            team_name=team_name,
            direction=direction,
            current_direction=current_direction,
        )

        if score is not None:
            scored_moves.append((score, direction))

    if scored_moves:
        scored_moves.sort(reverse=True, key=lambda item: item[0])
        score, direction = scored_moves[0]

        good_apples, bad_apples = get_items(field)

        print(
            f"SURVIVAL/CENTER MODE | Move={direction} | Score={score:.1f} | "
            f"Len={len(snake.body)} | Good={len(good_apples)} | Bad={len(bad_apples)}"
        )

        return direction

    print("NO SAFE MOVE FOUND. Continuing current direction.")
    return current_direction


# ============================================================
# MAIN LOOP
# ============================================================

def run_bot(
    team_name: str,
    game_name: str,
    password: str,
    base_url: str,
) -> None:
    current_direction: Direction = "EAST"

    api = SnakeFieldAPI(
        base_url=base_url,
        teamname=team_name,
        game_name=game_name,
        password=password,
        timeout=0.75,
    )

    print("Registering snake...")

    try:
        safe_set_direction(api, current_direction)
    except SystemExit:
        return

    wait_time = 0.5
    cooldown_after_error = 0.7

    while True:
        time.sleep(wait_time)

        try:
            field = safe_get_field(api)

            if field is None:
                time.sleep(cooldown_after_error)
                continue

            if team_name not in field.snakes:
                print(f"Team {team_name!r} not found yet.")
                continue

            snake = field.snakes[team_name]

            if not snake.alive:
                print("Snake is dead.")
                break

            current_direction = choose_direction(
                field=field,
                team_name=team_name,
                current_direction=current_direction,
            )

            posted = safe_set_direction(api, current_direction)

            if not posted:
                time.sleep(cooldown_after_error)

        except KeyboardInterrupt:
            print("Stopped by user.")
            break

        except SystemExit:
            break

        except Exception as error:
            print(f"Unexpected error: {error}")
            time.sleep(cooldown_after_error)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Snake game bot client")
    parser.add_argument("team_name", help="Name of the team/snake")
    parser.add_argument("game_name", help="Name of the game to join")
    parser.add_argument("--password", default="test", help="Password for server")
    parser.add_argument(
        "--base_url",
        default="http://localhost:3030",
        help="Base URL of the game server",
    )

    args = parser.parse_args()

    run_bot(
        team_name=args.team_name,
        game_name=args.game_name,
        password=args.password,
        base_url=args.base_url,
    )