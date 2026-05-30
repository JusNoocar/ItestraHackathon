from typing import Tuple, List, Set, Optional
import heapq

Coord = Tuple[int, int]

def neighbors(pos, width, height):
    x, y = pos
    return [((x+1)%width, y), ((x-1)%width, y), (x, (y+1)%height), (x, (y-1)%height)]

def heuristic(a: Coord, b: Coord, size: Tuple[int,int]) -> int:
    # toroidal manhattan
    dx = abs(a[0]-b[0])
    dy = abs(a[1]-b[1])
    w, h = size
    dx = min(dx, w-dx)
    dy = min(dy, h-dy)
    return dx+dy

def a_star(start: Coord, goal: Coord, blocked: Set[Coord], size: Tuple[int,int]) -> Optional[List[Coord]]:
    width, height = size
    openq = []
    heapq.heappush(openq, (0 + heuristic(start, goal, size), 0, start, None))
    came_from = {start: None}
    gscore = {start: 0}

    while openq:
        f, g, current, _ = heapq.heappop(openq)
        if current == goal:
            # reconstruct
            path = []
            cur = current
            while cur is not None:
                path.append(cur)
                cur = came_from.get(cur)
            path.reverse()
            return path

        for nbr in neighbors(current, width, height):
            if nbr in blocked:
                continue
            tentative_g = g + 1
            if tentative_g < gscore.get(nbr, 1e9):
                came_from[nbr] = current
                gscore[nbr] = tentative_g
                heapq.heappush(openq, (tentative_g + heuristic(nbr, goal, size), tentative_g, nbr, current))

    return None
