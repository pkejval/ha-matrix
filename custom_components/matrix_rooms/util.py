"""Utility helpers for Matrix Rooms."""

from __future__ import annotations

import re

ROOM_SPLIT_RE = re.compile(r"[\n,;]+")


def normalize_room_ids(value: str) -> list[str]:
    """Normalize a text blob into a list of room ids or aliases."""
    rooms = [room.strip() for room in ROOM_SPLIT_RE.split(value) if room.strip()]
    return list(dict.fromkeys(rooms))
