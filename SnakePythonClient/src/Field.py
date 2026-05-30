from dataclasses import dataclass, field
from typing import Dict, List, Tuple

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


def fill_info_from_source(source) -> [SnakeInfo]:
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

    @staticmethod
    def from_dict(raw: dict) -> "Field":
        size = tuple(raw["size"])
        snakes = ""
        if "snake" in raw:
            source = raw["snake"]
            snakes = fill_info_from_source(source)
        elif "snakes" in raw:
            source = raw["snakes"]
            snakes = fill_info_from_source(source)

        apples = []
        bad_apples = []
        
        if "apples" in raw:
            apples = [tuple(c) for c in raw["apples"]]
        
        if "items" in raw and isinstance(raw["items"], list):
            for entry in raw["items"]:
                # entry is [ [x, y], 'Type' ]
                if isinstance(entry, list) and len(entry) == 2:
                    coord_list, item_type = entry
                    coord = tuple(coord_list)
                    
                    if item_type == 'Apple':
                        apples.append(coord)
                    elif item_type == 'BadApple':
                        bad_apples.append(coord)

        return Field(size=size, snakes=snakes, apples=apples, bad_apples=bad_apples)