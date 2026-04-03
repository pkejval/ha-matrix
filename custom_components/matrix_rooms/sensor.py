"""Matrix Rooms sensor entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import get_client
from .const import EVENT_RECEIVED_NEW_MSG, EVENT_SEEN
from .room import iter_room_definitions


class MatrixRoomEventSensor(SensorEntity):
    """Track the last Matrix event for a configured room."""

    _attr_has_entity_name = True
    _attr_native_value = "idle"

    def __init__(self, client, entry: ConfigEntry, room: str, suffix: str) -> None:
        self._client = client
        self._entry = entry
        self._room = room
        self._attr_unique_id = f"{entry.entry_id}_event_{suffix}"
        self._attr_name = "Last event"
        self._unsub = None
        self._unsub2 = None
        self._attrs: dict[str, Any] = {}

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the latest event details."""
        return self._attrs

    @property
    def available(self) -> bool:
        """Return whether the Matrix client is ready."""
        return self._client.is_ready()

    async def async_added_to_hass(self) -> None:
        """Listen for Matrix bus events."""
        self._unsub = self.hass.bus.async_listen(EVENT_RECEIVED_NEW_MSG, self._handle_event)
        self._unsub2 = self.hass.bus.async_listen(EVENT_SEEN, self._handle_event)

    async def async_will_remove_from_hass(self) -> None:
        """Remove listeners."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        if self._unsub2 is not None:
            self._unsub2()
            self._unsub2 = None

    @callback
    def _handle_event(self, event) -> None:
        """Update from Matrix bus events."""
        data = event.data
        if data.get("entry_id") != self._entry.entry_id:
            return

        canonical_room = self._client.canonical_room_ref(self._room)
        if data.get("room_id") != canonical_room:
            return

        event_type = event.event_type
        if event_type == EVENT_RECEIVED_NEW_MSG:
            self._attr_native_value = f"{data.get('sender_name', data.get('sender', 'unknown'))}: {data.get('message', '')}"
        else:
            self._attr_native_value = f"seen by {data.get('seen_by_name', data.get('seen_by', 'unknown'))}"

        self._attrs = {"event_type": event_type, **dict(data)}
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matrix Rooms sensors."""
    client = get_client(hass, entry)
    entities = [
        MatrixRoomEventSensor(client, entry, room_def.room, room_def.entity_suffix)
        for room_def in iter_room_definitions({**entry.data, **entry.options})
    ]
    async_add_entities(entities)
