from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from data_structures import Coord, TeamName


@dataclass
class ActiveEffectInfo:
    effect: str
    remaining_ticks: int


@dataclass
class SnakeInfo:
    body: List[Coord]
    alive: bool
    inventory: List[str]
    active_effects: List[ActiveEffectInfo]


def fill_info_from_source(source) -> List[SnakeInfo]:
    snakes = {
        team: SnakeInfo(
            body=[tuple(coord) for coord in info["body"]],
            alive=info["alive"],
            inventory=list(info["inventory"]),
            active_effects=[
                ActiveEffectInfo(
                    effect=effect["effect"],
                    remaining_ticks=effect["remaining_ticks"],
                )
                for effect in info["active_effects"]
            ],
        )
        for team, info in source.items()
    }
    return snakes


@dataclass
class Field:
    size: Tuple[int, int]
    snakes: Dict[TeamName, SnakeInfo]
    apples: List[Coord] = field(default_factory=list)
    bad_apples: List[Coord] = field(default_factory=list)
    stars: List[Coord] = field(default_factory=list)
    star_every_ticks: Optional[int] = None
    instructions: List = field(default_factory=list)
    star_spawn_points: List[Coord] = field(default_factory=list)

    @staticmethod
    def from_dict(raw: dict) -> "Field":
        size = tuple(raw["size"])
        snakes = {}
        if "snake" in raw:
            source = raw["snake"]
            snakes = fill_info_from_source(source)
        elif "snakes" in raw:
            source = raw["snakes"]
            snakes = fill_info_from_source(source)

        apples: List[Coord] = []
        bad_apples: List[Coord] = []
        if "apples" in raw:
            apples = [tuple(coord) for coord in raw["apples"]]
        elif "food" in raw:
            apples = [tuple(coord) for coord in raw["food"]]

        if "bad_apples" in raw:
            bad_apples = [tuple(coord) for coord in raw["bad_apples"]]
        
        stars: List[Coord] = []
        if "items" in raw and isinstance(raw["items"], list):
            for item in raw["items"]:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    pos, kind = item
                    if isinstance(pos, (list, tuple)) and len(pos) == 2:
                        coord = tuple(pos)
                        if kind == "BadApple":
                            bad_apples.append(coord)
                        elif kind == "Apple":
                            apples.append(coord)
                        elif kind == "Star" or kind == "star":
                            stars.append(coord)
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
                        elif kind == "Star" or kind == "star":
                            stars.append(coord)
                        else:
                            apples.append(coord)

        # capture star spawn timing if present
        star_every_ticks = None
        if isinstance(raw.get("star_every_ticks"), int):
            star_every_ticks = raw.get("star_every_ticks")
        elif isinstance(raw.get("starEveryTicks"), int):
            star_every_ticks = raw.get("starEveryTicks")

        instructions = raw.get("instructions") if isinstance(raw.get("instructions"), list) else []
        star_spawn_points: List[Coord] = []
        for inst in instructions:
            try:
                if isinstance(inst, dict) and "Spawn" in inst:
                    spawn = inst["Spawn"]
                    if isinstance(spawn, list) and len(spawn) == 2 and (spawn[0] == "Star" or spawn[0] == "star"):
                        pos = spawn[1]
                        if isinstance(pos, (list, tuple)) and len(pos) == 2:
                            star_spawn_points.append(tuple(pos))
            except Exception:
                continue

        return Field(size=size, snakes=snakes, apples=apples, bad_apples=bad_apples, stars=stars, star_every_ticks=star_every_ticks, instructions=instructions, star_spawn_points=star_spawn_points)
