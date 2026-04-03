"""Room helpers for Matrix Rooms."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from homeassistant.util.slugify import slugify

from .const import CONF_ROOMS


@dataclass(slots=True, frozen=True)
class RoomDefinition:
    """A configured Matrix room."""

    room: str
    entity_suffix: str


def iter_room_definitions(config: dict[str, Any]) -> list[RoomDefinition]:
    """Return configured rooms with stable entity suffixes."""
    rooms = list(config.get(CONF_ROOMS, []))
    return [
        RoomDefinition(
            room=room,
            entity_suffix=f"{slugify(room).replace('-', '_')}_{hashlib.sha1(room.encode('utf-8')).hexdigest()[:8]}",
        )
        for room in rooms
    ]
