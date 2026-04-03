"""Matrix Rooms button entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.exceptions import HomeAssistantError

from .entity import get_client
from .room import iter_room_definitions, room_device_info


class MatrixRoomSendButton(ButtonEntity):
    """Send the current draft message to a Matrix room."""

    _attr_has_entity_name = True

    def __init__(self, client, entry: ConfigEntry, room: str, suffix: str) -> None:
        self._client = client
        self._entry = entry
        self._room = room
        self._attr_unique_id = f"{entry.entry_id}_send_{suffix}"
        self._attr_name = "Send message"
        self._attr_device_info = room_device_info(entry, room)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the target room."""
        return {"room_id": self._room}

    @property
    def available(self) -> bool:
        """Return whether the Matrix client is ready."""
        return self._client.is_ready()

    async def async_press(self) -> None:
        """Send the room's current draft message."""
        message = self._client.get_draft(self._room).strip()
        if not message:
            raise HomeAssistantError("Draft message is empty")

        await self._client.async_send_message(self._room, message)
        self._client.set_draft(self._room, "")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matrix Rooms buttons."""
    client = get_client(hass, entry)
    entities = [
        MatrixRoomSendButton(client, entry, room_def.room, room_def.entity_suffix)
        for room_def in iter_room_definitions({**entry.data, **entry.options})
    ]
    async_add_entities(entities)
