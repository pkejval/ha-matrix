"""Constants for Matrix Rooms."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "matrix_rooms"
NAME = "Matrix Rooms"

CONF_HOMESERVER = "homeserver"
CONF_ROOMS = "rooms"

ATTR_ENTRY_ID = "entry_id"
ATTR_ROOM_ID = "room_id"
ATTR_MESSAGE = "message"

SERVICE_SEND_MESSAGE = "send_message"

EVENT_SEEN = f"{DOMAIN}_seen"
EVENT_RECEIVED_NEW_MSG = f"{DOMAIN}_received_new_msg"

PLATFORMS = [Platform.SENSOR]
