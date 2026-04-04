"""Matrix Rooms sensor entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import get_client
from .const import (
    ATTR_ENTRY_ID,
    EVENT_LAST_MESSAGE_UPDATED,
    EVENT_LAST_SEEN_UPDATED,
    EVENT_RECEIVED_NEW_MSG,
    EVENT_SEEN,
)
from .room import iter_room_definitions, room_device_info, room_display_name


class _BaseMatrixRoomEventSensor(SensorEntity):
    """Base Matrix event sensor for a configured room."""

    _attr_has_entity_name = True
    _event_type: str
    _unique_id_prefix: str
    _sensor_name: str
    _default_native_value: str
    _default_attributes: dict[str, Any]

    def __init__(self, client, entry: ConfigEntry, room: str, suffix: str) -> None:
        self._client = client
        self._entry = entry
        self._room = room
        self._attr_unique_id = f"{entry.entry_id}_{self._unique_id_prefix}_{suffix}"
        self._attr_name = self._sensor_name
        self._unsub = None
        self._attr_native_value = self._default_native_value
        self._attrs = {
            "room_id": room,
            "room_name": room_display_name(room),
            **self._default_attributes,
        }

    @property
    def device_info(self):
        """Return the linked Matrix room device."""
        return room_device_info(self._entry, self._room)

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
        self._unsub = self.hass.bus.async_listen(self._event_type, self._handle_event)

    async def async_will_remove_from_hass(self) -> None:
        """Remove listeners."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    @callback
    def _handle_event(self, event) -> None:
        """Update from Matrix bus events."""
        data = event.data
        if data.get("entry_id") != self._entry.entry_id:
            return

        canonical_room = self._client.canonical_room_ref(self._room)
        if data.get("room_id") != canonical_room:
            return

        self._attr_native_value = self._format_native_value(data)
        self._attrs = {"event_type": event.event_type, **dict(data)}
        self.async_write_ha_state()
        self._async_fire_update_event(data)

    def _format_native_value(self, data: dict[str, Any]) -> str:
        """Format the state shown in the UI."""
        raise NotImplementedError

    def _async_fire_update_event(self, data: dict[str, Any]) -> None:
        """Fire a Matrix Rooms update event."""
        raise NotImplementedError


class MatrixRoomLastMessageSensor(_BaseMatrixRoomEventSensor):
    """Track the last Matrix message for a configured room."""

    _default_native_value = "waiting for message"
    _default_attributes = {"status": "waiting_for_message"}

    _event_type = EVENT_RECEIVED_NEW_MSG
    _unique_id_prefix = "last_message"
    _sensor_name = "Last message"

    def _format_native_value(self, data: dict[str, Any]) -> str:
        """Format the message state."""
        sender = data.get("sender_name", data.get("sender", "unknown"))
        message = data.get("message", "")
        return f"{sender}: {message}"

    def _async_fire_update_event(self, data: dict[str, Any]) -> None:
        """Fire the last-message update event."""
        self.hass.bus.async_fire(
            EVENT_LAST_MESSAGE_UPDATED,
            {
                ATTR_ENTRY_ID: self._entry.entry_id,
                "homeserver": self._client.homeserver,
                "room_id": data.get("room_id"),
                "room_name": data.get("room_name"),
                "message": data.get("message"),
                "msgtype": data.get("msgtype"),
                "url": data.get("url"),
                "sender": data.get("sender"),
                "sender_name": data.get("sender_name"),
                "self": data.get("self"),
                "event_id": data.get("event_id"),
                "timestamp": data.get("timestamp"),
            },
        )


class MatrixRoomLastSeenSensor(_BaseMatrixRoomEventSensor):
    """Track the last Matrix receipt for a configured room."""

    _default_native_value = "waiting for receipt"
    _default_attributes = {"status": "waiting_for_receipt"}

    _event_type = EVENT_SEEN
    _unique_id_prefix = "last_seen"
    _sensor_name = "Last seen"

    def _format_native_value(self, data: dict[str, Any]) -> str:
        """Format the receipt state."""
        seen_by = data.get("seen_by_name", data.get("seen_by", "unknown"))
        return f"seen by {seen_by}"

    def _async_fire_update_event(self, data: dict[str, Any]) -> None:
        """Fire the last-seen update event."""
        self.hass.bus.async_fire(
            EVENT_LAST_SEEN_UPDATED,
            {
                ATTR_ENTRY_ID: self._entry.entry_id,
                "homeserver": self._client.homeserver,
                "room_id": data.get("room_id"),
                "room_name": data.get("room_name"),
                "seen_by": data.get("seen_by"),
                "seen_by_name": data.get("seen_by_name"),
                "self": data.get("self"),
                "event_id": data.get("event_id"),
                "receipt_type": data.get("receipt_type"),
                "thread_id": data.get("thread_id"),
                "timestamp": data.get("timestamp"),
            },
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matrix Rooms sensors."""
    client = get_client(hass, entry)
    entities = []
    for room_def in iter_room_definitions({**entry.data, **entry.options}):
        entities.append(
            MatrixRoomLastMessageSensor(client, entry, room_def.room, room_def.entity_suffix)
        )
        entities.append(
            MatrixRoomLastSeenSensor(client, entry, room_def.room, room_def.entity_suffix)
        )
    async_add_entities(entities)
