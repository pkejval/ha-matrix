"""Matrix Rooms integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from time import time

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_ENTRY_ID,
    ATTR_MESSAGE,
    ATTR_ROOM_ID,
    DOMAIN,
    PLATFORMS,
    SERVICE_SEND_MESSAGE,
    EVENT_SENT_MSG,
)
from .room import (
    iter_room_definitions,
    room_device_identifier,
    room_device_registry_kwargs,
    room_display_name,
    server_device_registry_kwargs,
)

if TYPE_CHECKING:
    from .client import MatrixRoomsClient

SERVICE_SEND_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Required(ATTR_ROOM_ID): cv.string,
        vol.Required(ATTR_MESSAGE): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Matrix Rooms from a config entry."""
    from .client import MatrixRoomsClient

    domain_data = hass.data.setdefault(DOMAIN, {})
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(**server_device_registry_kwargs(entry))
    await _async_sync_room_devices(hass, entry, device_registry)

    if not domain_data.get("service_registered"):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            _async_send_message_service,
            schema=SERVICE_SEND_MESSAGE_SCHEMA,
        )
        domain_data["service_registered"] = True

    client = MatrixRoomsClient(hass, entry)
    entry.runtime_data = client
    domain_data[entry.entry_id] = client
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        await client.async_start()
    except Exception:
        await client.async_stop()
        domain_data.pop(entry.entry_id, None)
        entry.runtime_data = None
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    domain_data = hass.data.get(DOMAIN, {})
    client = domain_data.pop(entry.entry_id, None)

    if client is not None:
        await client.async_stop()

    entry.runtime_data = None
    return True


async def _async_sync_room_devices(
    hass: HomeAssistant, entry: ConfigEntry, device_registry: dr.DeviceRegistry
) -> None:
    """Create configured room devices and remove stale ones."""
    config = {**entry.data, **entry.options}
    configured_rooms = {room_def.room for room_def in iter_room_definitions(config)}
    expected_identifiers = {
        (DOMAIN, room_device_identifier(entry, room)) for room in configured_rooms
    }

    for room in configured_rooms:
        device_registry.async_get_or_create(**room_device_registry_kwargs(entry, room))

    stale_devices = [
        device
        for device in device_registry.devices.values()
        if entry.entry_id in device.config_entries
        and any(identifier[0] == DOMAIN and identifier[1].startswith(f"{entry.entry_id}:") for identifier in device.identifiers)
        and not any(identifier in expected_identifiers for identifier in device.identifiers)
    ]

    for device in stale_devices:
        device_registry.async_remove_device(device.id)


async def _async_send_message_service(call: ServiceCall) -> None:
    """Send a text message to a Matrix room."""
    hass = call.hass
    domain_data = hass.data.get(DOMAIN, {})

    entry_id = call.data.get(ATTR_ENTRY_ID)
    clients = [
        client
        for key, client in domain_data.items()
        if key != "service_registered"
    ]

    if entry_id:
        client = domain_data.get(entry_id)
        if client is None:
            raise HomeAssistantError(f"Unknown Matrix Rooms entry_id: {entry_id}")
    else:
        if len(clients) != 1:
            raise HomeAssistantError(
                "entry_id is required when more than one Matrix Rooms server is configured"
            )
        client = clients[0]

    response = await client.async_send_message(
        room_id=call.data[ATTR_ROOM_ID],
        message=call.data[ATTR_MESSAGE],
    )
    resolved_room = client.canonical_room_ref(call.data[ATTR_ROOM_ID])
    hass.bus.async_fire(
        EVENT_SENT_MSG,
        {
            ATTR_ENTRY_ID: client.entry.entry_id,
            "homeserver": client.homeserver,
            "room_id": resolved_room,
            "room_name": room_display_name(call.data[ATTR_ROOM_ID]),
            "sender": client.username,
            "sender_name": client.username,
            "self": True,
            "message": call.data[ATTR_MESSAGE],
            "msgtype": "m.text",
            "url": None,
            "event_id": getattr(response, "event_id", None),
            "timestamp": int(time() * 1000),
        },
    )
