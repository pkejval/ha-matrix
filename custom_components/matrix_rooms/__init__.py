"""Matrix Rooms integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
)
from .room import server_device_registry_kwargs

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

    await client.async_send_message(
        room_id=call.data[ATTR_ROOM_ID],
        message=call.data[ATTR_MESSAGE],
    )
