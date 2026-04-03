"""Room helpers for Matrix Rooms."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from .const import CONF_ROOMS


@dataclass(slots=True, frozen=True)
class RoomDefinition:
    """A configured Matrix room."""

    room: str
    entity_suffix: str


_ENTITY_SUFFIX_RE = re.compile(r"[^a-z0-9_]+")


def _slugify_room(room: str) -> str:
    """Return a stable slug for a Matrix room reference."""
    slug = room.lower().replace("#", "").replace("!", "")
    slug = slug.replace(":", "_").replace(".", "_").replace("-", "_")
    slug = _ENTITY_SUFFIX_RE.sub("_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "room"


def iter_room_definitions(config: dict[str, Any]) -> list[RoomDefinition]:
    """Return configured rooms with stable entity suffixes."""
    rooms = list(dict.fromkeys(config.get(CONF_ROOMS, [])))
    return [
        RoomDefinition(
            room=room,
            entity_suffix=f"{_slugify_room(room)}_{hashlib.sha1(room.encode('utf-8')).hexdigest()[:8]}",
        )
        for room in rooms
    ]
