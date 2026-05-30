from __future__ import annotations

import logging
from typing import Optional

import requests
from requests import Session
from requests.exceptions import RequestException

from Field import Field
from data_structures import Direction, ItemKind

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class SnakeFieldAPI:
    def __init__(
        self,
        base_url: str,
        teamname: str,
        game_name: str,
        password: str,
        *,
        timeout: float = 0.5,
        session: Optional[Session] = None,
    ) -> None:
        self.team_name = teamname
        self.game_name = game_name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.auth = (teamname, password)
        self.session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def get_field(self) -> Optional[Field]:
        url = self._url(f"/games/{self.game_name}/state")
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return Field.from_dict(data)
        except RequestException as exc:
            logger.warning("Failed to fetch field state: %s", exc)
            return None

    def set_direction(self, direction: Direction) -> bool:
        if direction not in ("NORTH", "SOUTH", "EAST", "WEST"):
            logger.warning("Attempted to set invalid direction: %s", direction)
            return False

        url = self._url(f"/games/{self.game_name}/snake/direction")
        payload = {"direction": direction}
        try:
            resp = self.session.post(url, json=payload, timeout=self.timeout)
            try:
                resp.raise_for_status()
            except RequestException as exc:
                logger.warning(
                    "Failed to set direction %s: status=%s body=%s",
                    direction,
                    resp.status_code,
                    resp.text,
                )
                return False
            return True
        except RequestException as exc:
            logger.warning("Failed to set direction %s: %s", direction, exc)
            return False

    def activate_item(self, item: ItemKind) -> None:
        url = self._url(f"/games/{self.game_name}/snake/activate")
        payload = {"item": item}
        self.session.post(url, json=payload, timeout=self.timeout)
