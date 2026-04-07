"""Constants for Matrix Rooms."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "matrix_rooms"
NAME = "Matrix Rooms"

CONF_HOMESERVER = "homeserver"
CONF_ROOMS = "rooms"
CONF_EMIT_GLOBAL_SEEN_EVENTS = "emit_global_seen_events"

ATTR_ENTRY_ID = "entry_id"
ATTR_ROOM_ID = "room_id"
ATTR_MESSAGE = "message"

SERVICE_SEND_MESSAGE = "send_message"

EVENT_SEEN = f"{DOMAIN}_seen"
EVENT_ANY_SEEN = f"{DOMAIN}_any_seen"
EVENT_RECEIVED_NEW_MSG = f"{DOMAIN}_received_new_msg"
EVENT_SENT_MSG = f"{DOMAIN}_sent_msg"
EVENT_LAST_MESSAGE_UPDATED = f"{DOMAIN}_last_message_updated"
EVENT_LAST_SEEN_UPDATED = f"{DOMAIN}_last_seen_updated"

PLATFORMS = [Platform.SENSOR]
