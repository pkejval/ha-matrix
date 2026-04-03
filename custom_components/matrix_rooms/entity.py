"""Shared entity helpers for Matrix Rooms."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .client import MatrixRoomsClient
from .const import DOMAIN


def get_client(hass: HomeAssistant, entry: ConfigEntry) -> MatrixRoomsClient:
    """Return the runtime client for an entry."""
    client = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if client is None:
        raise HomeAssistantError(
            f"Matrix Rooms client is not available for {entry.entry_id}"
        )
    return client
