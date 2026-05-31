from __future__ import annotations

import argparse
import math
import random
import time
from collections import deque
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import requests

Coord = Tuple[int, int]
Direction = str

DIRECTIONS: Dict[Direction, Coord] = {
    "NORTH": (0, -1),
    "SOUTH": (0, 1),
    "WEST": (-1, 0),
    "EAST": (1, 0),
}

OPPOSITE: Dict[Direction, Direction] = {
    "NORTH": "SOUTH",
    "SOUTH": "NORTH",
    "WEST": "EAST",
    "EAST": "WEST",
}

ITEM_VALUE: Dict[str, float] = {
    "Star": 1200.0,
    "Sword": 850.0,
    "SpeedBoost": 780.0,
    "InstantStack": 700.0,
    "Apple": 250.0,
    "BadApple": -900.0,
}

POWER_ITEMS = {"Star", "Sword", "SpeedBoost", "InstantStack"}
GOOD_ITEMS = {"Star", "Sword", "SpeedBoost", "InstantStack", "Apple"}


class SnakeAPI:
    def __init__(self, base_url: str, team_name: str, game_name: str, password: str, timeout: float = 0.45) -> None:
        self.base_url = base_url.rstrip("/")
        self.team_name = team_name
        self.game_name = game_name
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = (team_name, password)
        self.session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    def _url(self, suffix: str) -> str:
        return f"{self.base_url}/games/{self.game_name}{suffix}"

    def state(self) -> Dict[str, Any]:
        response = self.session.get(self._url("/state"), timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def set_direction(self, direction: Direction) -> None:
        try:
            self.session.post(self._url("/snake/direction"), json={"direction": direction}, timeout=self.timeout)
        except requests.RequestException:
            pass

    def activate(self, item: str) -> None:
        try:
            self.session.post(self._url("/snake/activate"), json={"item": item}, timeout=self.timeout)
        except requests.RequestException:
            pass


def wrap(pos: Coord, size: Coord) -> Coord:
    return pos[0] % size[0], pos[1] % size[1]


def step(pos: Coord, direction: Direction, size: Coord) -> Coord:
    dx, dy = DIRECTIONS[direction]
    return wrap((pos[0] + dx, pos[1] + dy), size)


def torus_delta(a: int, b: int, modulus: int) -> int:
    raw = b - a
    if raw > modulus // 2:
        raw -= modulus
    if raw < -modulus // 2:
        raw += modulus
    return raw


def torus_dist(a: Coord, b: Coord, size: Coord) -> int:
    return abs(torus_delta(a[0], b[0], size[0])) + abs(torus_delta(a[1], b[1], size[1]))


def normalize_coord(value: Any) -> Optional[Coord]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return int(value[0]), int(value[1])
        except (TypeError, ValueError):
            return None
    return None


def parse_snakes(raw: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    source = raw.get("snakes", raw.get("snake", {}))
    if not isinstance(source, dict):
        return {}

    snakes: Dict[str, Dict[str, Any]] = {}
    for team, info in source.items():
        if not isinstance(info, dict):
            continue
        body = [c for c in (normalize_coord(x) for x in info.get("body", [])) if c is not None]
        inventory = info.get("inventory", info.get("items", []))
        if not isinstance(inventory, list):
            inventory = []
        active_effects = info.get("active_effects", [])
        if not isinstance(active_effects, list):
            active_effects = []
        snakes[str(team)] = {
            "body": body,
            "alive": bool(info.get("alive", True)),
            "inventory": [str(x) for x in inventory],
            "active_effects": active_effects,
        }
    return snakes


def parse_items(raw: Dict[str, Any]) -> Dict[Coord, str]:
    items: Dict[Coord, str] = {}

    raw_items = raw.get("items", raw.get("item", []))
    if isinstance(raw_items, dict):
        iterable: Iterable[Any] = raw_items.values()
    elif isinstance(raw_items, list):
        iterable = raw_items
    else:
        iterable = []

    for entry in iterable:
        pos: Optional[Coord] = None
        kind: Optional[str] = None

        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
            if isinstance(entry[0], (list, tuple)):
                pos = normalize_coord(entry[0])
                kind = str(entry[1])
            elif isinstance(entry[1], (list, tuple)):
                kind = str(entry[0])
                pos = normalize_coord(entry[1])

        # Possible object format.
        if isinstance(entry, dict):
            pos = normalize_coord(entry.get("position", entry.get("coord", entry.get("pos"))))
            kind = entry.get("kind", entry.get("type", entry.get("item")))
            if kind is not None:
                kind = str(kind)

        if pos is not None and kind is not None:
            items[pos] = kind

    return items


def infer_direction(body: Sequence[Coord], fallback: Direction, size: Coord) -> Direction:
    if len(body) < 2:
        return fallback
    head, neck = body[0], body[1]
    for direction in DIRECTIONS:
        if step(neck, direction, size) == head:
            return direction
    return fallback


def occupied_cells(snakes: Dict[str, Dict[str, Any]], own_team: str) -> Set[Coord]:
    occupied: Set[Coord] = set()
    for team, snake in snakes.items():
        if not snake["alive"]:
            continue
        body = snake["body"]
        if not body:
            continue

        # Be slightly optimistic about our own tail because it normally moves away.
        # Keep all enemy tails blocked because they may grow or item effects may alter movement.
        cells = body[:-1] if team == own_team and len(body) > 1 else body
        occupied.update(cells)
    return occupied


def enemy_heads(snakes: Dict[str, Dict[str, Any]], own_team: str) -> List[Coord]:
    heads: List[Coord] = []
    for team, snake in snakes.items():
        if team != own_team and snake["alive"] and snake["body"]:
            heads.append(snake["body"][0])
    return heads


def enemy_possible_next_cells(heads: Sequence[Coord], size: Coord) -> Set[Coord]:
    cells: Set[Coord] = set()
    for head in heads:
        for direction in DIRECTIONS:
            cells.add(step(head, direction, size))
    return cells


def flood_fill(start: Coord, blocked: Set[Coord], size: Coord, limit: int = 600) -> int:
    if start in blocked:
        return 0

    queue = deque([start])
    seen = {start}

    while queue and len(seen) < limit:
        pos = queue.popleft()
        for direction in DIRECTIONS:
            nxt = step(pos, direction, size)
            if nxt not in seen and nxt not in blocked:
                seen.add(nxt)
                queue.append(nxt)

    return len(seen)


def exit_count(pos: Coord, blocked: Set[Coord], size: Coord) -> int:
    return sum(1 for direction in DIRECTIONS if step(pos, direction, size) not in blocked)


def nearest_item_bonus(pos: Coord, items: Dict[Coord, str], size: Coord) -> float:
    best = 0.0
    for item_pos, kind in items.items():
        value = ITEM_VALUE.get(kind, 0.0)
        if value <= 0:
            continue
        distance = max(1, torus_dist(pos, item_pos, size))
        # Nearby powerups matter much more than far-away ones.
        best = max(best, value / distance)
    return best


def choose_direction(
    team: str,
    raw: Dict[str, Any],
    last_direction: Direction,
) -> Tuple[Direction, Dict[Direction, float]]:
    size = tuple(raw.get("size", (41, 41)))  # type: ignore[arg-type]
    size = (int(size[0]), int(size[1]))

    snakes = parse_snakes(raw)
    own = snakes.get(team)

    if own is None or not own["body"]:
        return last_direction, {last_direction: 0.0}

    body: List[Coord] = own["body"]
    head = body[0]
    current_direction = infer_direction(body, last_direction, size)

    blocked = occupied_cells(snakes, team)
    heads = enemy_heads(snakes, team)
    enemy_next = enemy_possible_next_cells(heads, size)
    items = parse_items(raw)
    center = (size[0] // 2, size[1] // 2)

    scores: Dict[Direction, float] = {}
    for direction in DIRECTIONS:
        first = step(head, direction, size)

        # Avoid instant 180-degree reversal when the neck is a real separate cell.
        if len(body) > 1 and body[1] != head and direction == OPPOSITE.get(current_direction):
            scores[direction] = -2_000_000.0
            continue

        if first in blocked:
            scores[direction] = -1_000_000.0
            continue

        score = 0.0
        score += 10_000.0

        ff = flood_fill(first, blocked, size, limit=max(200, size[0] * size[1]))
        score += ff * 18.0

        exits = exit_count(first, blocked, size)
        score += exits * 120.0
        if exits <= 1:
            score -= 1200.0
        elif exits == 2:
            score -= 250.0

        # Direct item on next cell.
        item_here = items.get(first)
        if item_here:
            score += ITEM_VALUE.get(item_here, 0.0)

        # Special final-round center rule: exact center is often a BadApple and a traffic trap.
        if first == center:
            score -= 1600.0
        center_distance = torus_dist(first, center, size)
        if 2 <= center_distance <= 5:
            score += 160.0
        elif center_distance <= 1:
            score -= 350.0

        # Enemy danger.
        if first in enemy_next:
            score -= 900.0

        adjacent_enemy_heads = sum(1 for h in heads if torus_dist(first, h, size) <= 1)
        near_enemy_heads = sum(1 for h in heads if torus_dist(first, h, size) <= 2)
        score -= adjacent_enemy_heads * 700.0
        score -= near_enemy_heads * 200.0

        # Prefer continuing straight when all else is equal, but not too much.
        if direction == current_direction:
            score += 90.0

        # Pull toward useful nearby items, but do not override survival.
        score += nearest_item_bonus(first, items, size) * 2.2

        # Random tiny tie-breaker prevents deterministic collision with mirror bots.
        score += random.random() * 3.0

        scores[direction] = score

    best_direction = max(scores, key=scores.get)
    if scores[best_direction] < -900_000:
        # Absolute emergency: pick any direction, preferably not reverse.
        legal = [d for d in DIRECTIONS if d != OPPOSITE.get(current_direction)]
        best_direction = random.choice(legal or list(DIRECTIONS))

    return best_direction, scores


def cell_safe(pos: Coord, blocked: Set[Coord]) -> bool:
    return pos not in blocked


def should_activate_item(team: str, raw: Dict[str, Any], direction: Direction) -> Optional[str]:
    size = tuple(raw.get("size", (41, 41)))  # type: ignore[arg-type]
    size = (int(size[0]), int(size[1]))

    snakes = parse_snakes(raw)
    own = snakes.get(team)
    if own is None or not own["body"] or not own["alive"]:
        return None

    inventory = set(own.get("inventory", []))
    if not inventory:
        return None

    body: List[Coord] = own["body"]
    head = body[0]
    first = step(head, direction, size)
    second = step(first, direction, size)
    blocked = occupied_cells(snakes, team)
    heads = enemy_heads(snakes, team)
    items = parse_items(raw)
    center = (size[0] // 2, size[1] // 2)

    enemy_close = any(torus_dist(head, h, size) <= 3 for h in heads)
    enemy_can_contest_first = first in enemy_possible_next_cells(heads, size)
    near_center = torus_dist(head, center, size) <= 7

    # Star: if activatable, use it for center fights or enemy contact.
    if "Star" in inventory and (enemy_close or near_center):
        return "Star"

    # Sword: 42-style aggression, but only when contact/contest is plausible.
    if "Sword" in inventory and (enemy_close or enemy_can_contest_first or near_center):
        return "Sword"

    # SpeedBoost: Titanaboa-style mobility with strict 2-cell safety.
    if "SpeedBoost" in inventory:
        second_item = items.get(second)
        second_value = ITEM_VALUE.get(second_item or "", 0.0)
        second_space = flood_fill(second, blocked, size, limit=max(200, size[0] * size[1]))
        second_enemy_risk = any(torus_dist(second, h, size) <= 1 for h in heads)
        bad_center_path = first == center or second == center

        if (
            cell_safe(first, blocked)
            and cell_safe(second, blocked)
            and not second_enemy_risk
            and not bad_center_path
            and (
                second_value >= ITEM_VALUE["Apple"]
                or second_space > len(body) + 25
                or (near_center and second_value > 0)
            )
        ):
            return "SpeedBoost"

    # InstantStack: likely score/growth; use when not in immediate cramped danger.
    if "InstantStack" in inventory:
        space_here = flood_fill(first, blocked, size, limit=max(200, size[0] * size[1]))
        if space_here > len(body) + 15 and not enemy_can_contest_first:
            return "InstantStack"

    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Boss-final Snake bot")
    parser.add_argument("team_name", help="Name of the team/snake")
    parser.add_argument("game_name", help="Name of the game, e.g. Final")
    parser.add_argument("--password", default="test", help="Password for server")
    parser.add_argument("--base_url", default="http://localhost:3030", help="Base URL, e.g. http://192.168.7.211:3030")
    parser.add_argument("--tick_seconds", type=float, default=0.92, help="Client loop interval. Keep below/near server tick, not spammy.")
    args = parser.parse_args()

    api = SnakeAPI(args.base_url, args.team_name, args.game_name, args.password)

    last_direction: Direction = "NORTH"
    last_activation_tick = -999999
    tick = 0

    # Register once.
    api.set_direction(last_direction)

    while True:
        loop_start = time.monotonic()

        try:
            raw = api.state()
            snakes = parse_snakes(raw)
            own = snakes.get(args.team_name)

            if own is not None and own["alive"] is False:
                print("Snake is dead. Stopping.")
                return

            direction, scores = choose_direction(args.team_name, raw, last_direction)
            last_direction = direction

            # At most one activation per loop. No spamming.
            item_to_activate = should_activate_item(args.team_name, raw, direction)
            if item_to_activate is not None and tick - last_activation_tick >= 1:
                api.activate(item_to_activate)
                last_activation_tick = tick

            api.set_direction(direction)

            compact_scores = " ".join(f"{d}:{scores.get(d, 0):.0f}" for d in ("NORTH", "EAST", "SOUTH", "WEST"))
            inv = own.get("inventory", []) if own else []
            print(f"tick={tick:05d} dir={direction:5s} item={item_to_activate or '-':12s} inv={inv} {compact_scores}")

        except KeyboardInterrupt:
            return
        except Exception as exc:
            # Network hiccup or unexpected JSON should not crash the bot during finals.
            print(f"recoverable error: {type(exc).__name__}: {exc}")
            api.set_direction(last_direction)

        tick += 1
        elapsed = time.monotonic() - loop_start
        time.sleep(max(0.05, args.tick_seconds - elapsed))


if __name__ == "__main__":
    main()

