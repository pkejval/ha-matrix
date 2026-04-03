"""Matrix client management."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from nio import AsyncClient, MatrixRoom, RoomMessageText
from nio.client.async_client import AsyncClientConfig
from nio.events.ephemeral import ReceiptEvent
from nio.responses import (
    ErrorResponse,
    JoinError,
    JoinResponse,
    LoginError,
    Response,
    RoomResolveAliasResponse,
    WhoamiError,
    WhoamiResponse,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.storage import Store

from .const import (
    ATTR_ENTRY_ID,
    ATTR_MESSAGE,
    ATTR_ROOM_ID,
    CONF_HOMESERVER,
    CONF_ROOMS,
    DOMAIN,
    EVENT_RECEIVED_NEW_MSG,
    EVENT_SEEN,
)
_LOGGER = logging.getLogger(__name__)
_SESSION_FILE_PREFIX = ".matrix_rooms_"
_SYNC_TIMEOUT_MS = 30_000
_SYNC_LOOP_SLEEP_MS = 1_000
_SERVICE_READY_TIMEOUT = 30


class MatrixRoomsClient:
    """Matrix client wrapper for a single config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        config = {**entry.data, **entry.options}
        self._homeserver: str = config[CONF_HOMESERVER]
        self._username: str = config[CONF_USERNAME]
        self._password: str = config[CONF_PASSWORD]
        self._verify_ssl: bool = config[CONF_VERIFY_SSL]
        self._configured_rooms: list[str] = list(config.get(CONF_ROOMS, []))
        self._store_path = hass.config.path(f"{_SESSION_FILE_PREFIX}{entry.entry_id}")
        self._session_store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self._ready = asyncio.Event()
        self._startup_error: BaseException | None = None
        self._draft_messages: dict[str, str] = {}
        self._draft_listeners: dict[str, list[Callable[[str], None]]] = {}
        self._room_refs: dict[str, str] = {}
        self._callbacks_registered = False
        self._client = AsyncClient(
            homeserver=self._homeserver,
            user=self._username,
            store_path=self._store_path,
            config=AsyncClientConfig(store_sync_tokens=True),
            ssl=self._verify_ssl,
        )
        self._sync_task: asyncio.Task[None] | None = None
        self._resolved_rooms: dict[str, str] = {}

    async def async_start(self) -> None:
        """Start the Matrix runner in the background."""
        if self._sync_task is not None:
            return

        self._sync_task = self.hass.async_create_task(
            self._async_run(),
            name=f"{DOMAIN}:sync:{self.entry.entry_id}",
        )

        try:
            await asyncio.wait_for(self._ready.wait(), timeout=_SERVICE_READY_TIMEOUT)
        except asyncio.TimeoutError as err:
            await self.async_stop()
            raise ConfigEntryNotReady(
                f"Matrix client did not become ready within {_SERVICE_READY_TIMEOUT} seconds"
            ) from err

        if self._startup_error is not None:
            startup_error = self._startup_error
            await self.async_stop()
            if isinstance(startup_error, ConfigEntryAuthFailed):
                raise startup_error
            raise ConfigEntryNotReady(
                "Matrix client failed during startup"
            ) from startup_error

    async def async_stop(self) -> None:
        """Stop the sync task and close the client."""
        if self._sync_task is not None:
            self._sync_task.cancel()
            await asyncio.gather(self._sync_task, return_exceptions=True)
            self._sync_task = None

        self._ready.clear()
        self._startup_error = None

        await self._client.close()

    async def async_send_message(self, room_id: str, message: str) -> None:
        """Send a plain text message to a Matrix room."""
        await self._async_wait_until_ready()
        resolved_room = self._canonical_room_ref(room_id)
        response: Response = await self._client.room_send(
            room_id=resolved_room,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": message,
            },
        )

        if isinstance(response, ErrorResponse):
            raise HomeAssistantError(
                f"Unable to deliver message to room '{room_id}': {response}"
            )

    def get_draft(self, room_id: str) -> str:
        """Return the current draft message for a room."""
        return self._draft_messages.get(self._canonical_room_ref(room_id), "")

    def set_draft(self, room_id: str, message: str) -> None:
        """Update the current draft message for a room."""
        canonical_room = self._canonical_room_ref(room_id)
        self._draft_messages[canonical_room] = message
        for callback in self._draft_listeners.get(canonical_room, []):
            callback(message)

    def add_draft_listener(self, room_id: str, callback: Callable[[str], None]) -> Callable[[], None]:
        """Register a draft listener and return an unsubscribe callback."""
        canonical_room = self._canonical_room_ref(room_id)
        listeners = self._draft_listeners.setdefault(canonical_room, [])
        listeners.append(callback)

        def _unsubscribe() -> None:
            listeners[:] = [item for item in listeners if item is not callback]

        return _unsubscribe

    def is_ready(self) -> bool:
        """Return whether the client has completed a successful startup."""
        return self._ready.is_set() and self._startup_error is None

    def canonical_room_ref(self, room_id_or_alias: str) -> str:
        """Return the canonical room id for a configured room reference."""
        return self._canonical_room_ref(room_id_or_alias)

    async def _async_run(self) -> None:
        """Login, join rooms and keep sync running with backoff."""
        backoff = 1

        try:
            while True:
                try:
                    self._startup_error = None
                    self._ready.clear()
                    await self._async_login()
                    await self._async_resolve_and_join_rooms()
                    if not self._callbacks_registered:
                        self._client.add_event_callback(
                            self._async_handle_message,
                            RoomMessageText,
                        )
                        self._client.add_event_callback(
                            self._async_handle_receipt,
                            ReceiptEvent,
                        )
                        self._callbacks_registered = True
                    self._ready.set()
                    await self._client.sync_forever(
                        timeout=_SYNC_TIMEOUT_MS,
                        loop_sleep_time=_SYNC_LOOP_SLEEP_MS,
                        full_state=True,
                    )
                    backoff = 1
                except asyncio.CancelledError:
                    raise
                except ConfigEntryAuthFailed as err:
                    self._startup_error = err
                    self._ready.set()
                    _LOGGER.error("Matrix authentication failed for %s", self._username)
                    return
                except Exception:
                    _LOGGER.exception(
                        "Matrix runtime failed for %s, retrying in %s seconds",
                        self._username,
                        backoff,
                    )
                    self._ready.clear()
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 300)
        except asyncio.CancelledError:
            raise
        except BaseException as err:
            self._startup_error = err
            self._ready.set()
            _LOGGER.exception("Matrix startup failed for %s", self._username)
        finally:
            self._ready.set()

    async def _async_login(self) -> None:
        """Restore the previous access token or log in with a password."""
        access_token = await self._async_load_access_token()

        if access_token:
            self._client.restore_login(**access_token)
            whoami = await self._client.whoami()
            if isinstance(whoami, WhoamiResponse):
                _LOGGER.debug("Restored Matrix login for %s", self._username)
                return

            if isinstance(whoami, WhoamiError):
                _LOGGER.warning(
                    "Could not restore Matrix login for %s: %s %s",
                    self._username,
                    whoami.status_code,
                    whoami.message,
                )
                self._client.access_token = ""

        login = await self._client.login(password=self._password)
        if isinstance(login, LoginError) or not self._client.logged_in:
            raise ConfigEntryAuthFailed(
                "Matrix login failed with the configured username and password"
            )

        await self._async_store_access_token()
        _LOGGER.debug("Logged into Matrix as %s", self._username)

    async def _async_load_access_token(self) -> dict[str, str] | None:
        """Load the cached access token from disk."""
        data = await self._session_store.async_load()

        if not isinstance(data, dict):
            return None

        token = data.get(self._username)
        if isinstance(token, str) and token:
            return {
                "user_id": self._username,
                "device_id": "",
                "access_token": token,
            }

        if not isinstance(token, dict):
            return None

        access_token = token.get("access_token")
        device_id = token.get("device_id", "")
        user_id = token.get("user_id", self._username)
        if not isinstance(access_token, str) or not access_token:
            return None

        return {
            "user_id": user_id if isinstance(user_id, str) and user_id else self._username,
            "device_id": device_id if isinstance(device_id, str) else "",
            "access_token": access_token,
        }

    async def _async_store_access_token(self) -> None:
        """Store the access token to disk."""
        current = await self._session_store.async_load()
        if not isinstance(current, dict):
            current = {}

        current[self._username] = {
            "access_token": self._client.access_token,
            "device_id": self._client.device_id or "",
            "user_id": self._client.user_id or self._username,
        }
        await self._session_store.async_save(current)

    async def _async_resolve_and_join_rooms(self) -> None:
        """Resolve aliases and join the configured rooms."""
        for original_room in self._configured_rooms:
            room_id = await self._async_resolve_room_id(original_room)
            self._room_refs[original_room] = room_id
            self._room_refs[room_id] = room_id
            self._resolved_rooms[original_room] = room_id
            self._resolved_rooms[room_id] = room_id
            await self._async_join_room(room_id, original_room)

    async def _async_join_room(self, room_id: str, original_room: str) -> None:
        """Join a room if needed."""
        join_response = await self._client.join(room_id)
        if isinstance(join_response, JoinResponse):
            _LOGGER.debug("Joined Matrix room %s (configured as %s)", room_id, original_room)
            return

        if isinstance(join_response, JoinError):
            _LOGGER.warning(
                "Could not join Matrix room %s: %s %s",
                original_room,
                join_response.status_code,
                join_response.message,
            )

    async def _async_resolve_room_id(self, room_id_or_alias: str) -> str:
        """Resolve a room alias or return the room id unchanged."""
        if room_id_or_alias.startswith("!"):
            return room_id_or_alias

        if room_id_or_alias in self._resolved_rooms:
            return self._resolved_rooms[room_id_or_alias]

        if not room_id_or_alias.startswith("#"):
            return room_id_or_alias

        response = await self._client.room_resolve_alias(room_id_or_alias)
        if isinstance(response, RoomResolveAliasResponse):
            return response.room_id

        raise HomeAssistantError(
            f"Unable to resolve Matrix room alias '{room_id_or_alias}': {response}"
        )

    @callback
    def _async_handle_message(self, room: MatrixRoom, event: RoomMessageText) -> None:
        """Forward received text messages to the Home Assistant event bus."""
        sender_name = self._async_get_user_name(room, event.sender)
        self.hass.bus.async_fire(
            EVENT_RECEIVED_NEW_MSG,
            {
                ATTR_ENTRY_ID: self.entry.entry_id,
                "homeserver": self._homeserver,
                "room_id": room.room_id,
                "room_name": getattr(room, "display_name", room.room_id),
                "sender": event.sender,
                "sender_name": sender_name,
                "self": event.sender == self._client.user_id,
                "message": event.body,
                "event_id": event.event_id,
                "timestamp": self._async_get_event_timestamp(event),
            },
        )

    @callback
    def _async_handle_receipt(self, room: MatrixRoom, event: ReceiptEvent) -> None:
        """Forward read receipts to the Home Assistant event bus."""
        for receipt in event.receipts:
            self.hass.bus.async_fire(
                EVENT_SEEN,
                {
                    ATTR_ENTRY_ID: self.entry.entry_id,
                    "homeserver": self._homeserver,
                    "room_id": room.room_id,
                    "room_name": getattr(room, "display_name", room.room_id),
                    "seen_by": receipt.user_id,
                    "seen_by_name": self._async_get_user_name(room, receipt.user_id),
                    "self": receipt.user_id == self._client.user_id,
                    "event_id": receipt.event_id,
                    "receipt_type": str(getattr(receipt, "receipt_type", "m.read")),
                    "thread_id": getattr(receipt, "thread_id", None),
                    "timestamp": getattr(receipt, "timestamp", None),
                },
            )

    async def _async_wait_until_ready(self) -> None:
        """Wait for the first successful startup or fail fast."""
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=_SERVICE_READY_TIMEOUT)
        except asyncio.TimeoutError as err:
            raise HomeAssistantError("Matrix client is not ready") from err
        if self._startup_error is not None:
            raise HomeAssistantError("Matrix client startup failed") from self._startup_error

    def _canonical_room_ref(self, room_id_or_alias: str) -> str:
        """Return the canonical room id for a configured room reference."""
        return self._room_refs.get(
            room_id_or_alias,
            self._resolved_rooms.get(room_id_or_alias, room_id_or_alias),
        )

    def _async_get_user_name(self, room: MatrixRoom, user_id: str) -> str:
        """Best-effort display name lookup."""
        try:
            return room.user_name(user_id)
        except Exception:  # noqa: BLE001
            return user_id

    @staticmethod
    def _async_get_event_timestamp(event: RoomMessageText) -> int | None:
        """Return the Matrix event timestamp if available."""
        for attr_name in ("server_timestamp", "origin_server_ts", "timestamp"):
            value = getattr(event, attr_name, None)
            if isinstance(value, int):
                return value

        source = getattr(event, "source", None)
        if isinstance(source, dict):
            value = source.get("origin_server_ts")
            if isinstance(value, int):
                return value

        return None
