"""Matrix Rooms text entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .entity import get_client
from .room import iter_room_definitions, room_device_info


class MatrixRoomMessageText(TextEntity, RestoreEntity):
    """Compose a Matrix message for a room."""

    _attr_has_entity_name = True
    _attr_mode = TextMode.TEXT
    _attr_native_max = 4000
    _attr_native_min = 0

    def __init__(self, client, entry: ConfigEntry, room: str, suffix: str) -> None:
        self._client = client
        self._entry = entry
        self._room = room
        self._attr_unique_id = f"{entry.entry_id}_message_{suffix}"
        self._attr_name = "Message draft"
        self._attr_native_value = ""
        self._unsubscribe = None
        self._attr_device_info = room_device_info(entry, room)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the target room."""
        return {"room_id": self._room}

    @property
    def available(self) -> bool:
        """Return whether the Matrix client is ready."""
        return self._client.is_ready()

    async def async_added_to_hass(self) -> None:
        """Restore the last typed draft."""
        await super().async_added_to_hass()
        self._attr_native_value = self._client.get_draft(self._room)
        if not self._attr_native_value:
            if (restored := await self.async_get_last_state()) and restored.state not in (
                None,
                "unknown",
                "unavailable",
            ):
                self._attr_native_value = restored.state

        if self._attr_native_value:
            self._client.set_draft(self._room, self._attr_native_value)

        self._unsubscribe = self._client.add_draft_listener(
            self._room,
            self._handle_draft_update,
        )

    async def async_set_value(self, value: str) -> None:
        """Update the draft text."""
        self._attr_native_value = value
        self._client.set_draft(self._room, value)
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Remove the draft listener."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    def _handle_draft_update(self, value: str) -> None:
        """Update state from the shared client draft."""
        self._attr_native_value = value
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matrix Rooms text entities."""
    client = get_client(hass, entry)
    entities = [
        MatrixRoomMessageText(client, entry, room_def.room, room_def.entity_suffix)
        for room_def in iter_room_definitions({**entry.data, **entry.options})
    ]
    async_add_entities(entities)
