"""Room helpers for Matrix Rooms."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from homeassistant.const import CONF_USERNAME

from .const import CONF_HOMESERVER, CONF_ROOMS, DOMAIN


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


def room_display_name(room: str) -> str:
    """Return a human-friendly Matrix room label."""
    return room.lstrip("#!") or room


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


def server_device_identifier(entry: ConfigEntry) -> str:
    """Return the stable identifier for the Matrix homeserver device."""
    return entry.entry_id


def room_device_identifier(entry: ConfigEntry, room: str) -> str:
    """Return the stable identifier for a Matrix room device."""
    return f"{entry.entry_id}:{room}"


def server_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return the device info for the Matrix homeserver device."""
    config = {**entry.data, **entry.options}
    homeserver = config[CONF_HOMESERVER]
    username = config.get(CONF_USERNAME, entry.title)
    return DeviceInfo(
        identifiers={(DOMAIN, server_device_identifier(entry))},
        name=f"{username} @ {homeserver}",
        entry_type=DeviceEntryType.SERVICE,
        default_manufacturer="Matrix",
        default_model="Homeserver",
        configuration_url=homeserver,
    )


def server_device_registry_kwargs(entry: ConfigEntry) -> dict[str, Any]:
    """Return registry kwargs for the Matrix homeserver device."""
    config = {**entry.data, **entry.options}
    homeserver = config[CONF_HOMESERVER]
    username = config.get(CONF_USERNAME, entry.title)
    return {
        "config_entry_id": entry.entry_id,
        "identifiers": {(DOMAIN, server_device_identifier(entry))},
        "name": f"{username} @ {homeserver}",
        "entry_type": DeviceEntryType.SERVICE,
        "manufacturer": "Matrix",
        "model": "Homeserver",
        "configuration_url": homeserver,
    }


def room_device_info(entry: ConfigEntry, room: str) -> DeviceInfo:
    """Return the device info for a Matrix room device."""
    return DeviceInfo(
        identifiers={(DOMAIN, room_device_identifier(entry, room))},
        name=room_display_name(room),
        via_device=(DOMAIN, server_device_identifier(entry)),
        default_manufacturer="Matrix",
        default_model="Room",
    )
