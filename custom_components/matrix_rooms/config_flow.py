"""Config flow for Matrix Rooms."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .const import CONF_HOMESERVER, CONF_ROOMS, DOMAIN
def _parse_room(value: str) -> str:
    """Parse a single room id or alias from a text field."""
    room = value.strip()
    if not room or not room.startswith(("!", "#")):
        raise vol.Invalid(
            "Room must be a Matrix room id or alias starting with ! or #"
        )
    return room


def _validate_homeserver(value: str) -> str:
    """Validate and normalize the homeserver URL."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise vol.Invalid("Homeserver must be a valid http(s) URL")
    return value.rstrip("/")


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the base config schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOMESERVER, default=defaults.get(CONF_HOMESERVER, "")): cv.string,
            vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): cv.string,
            vol.Required(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): cv.string,
            vol.Optional(
                CONF_VERIFY_SSL,
                default=defaults.get(CONF_VERIFY_SSL, True),
            ): cv.boolean,
        }
    )


def _rooms_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the single-room schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_ROOMS,
                default=defaults.get(CONF_ROOMS, ""),
            ): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
        }
    )


class MatrixRoomsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Matrix Rooms."""

    VERSION = 1

    def __init__(self) -> None:
        self._user_input: dict[str, Any] = {}
        self._rooms: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                user_input[CONF_HOMESERVER] = _validate_homeserver(
                    user_input[CONF_HOMESERVER]
                )
            except vol.Invalid:
                errors[CONF_HOMESERVER] = "invalid_homeserver"
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOMESERVER]}|{user_input[CONF_USERNAME]}"
                )
                self._abort_if_unique_id_configured()
                self._user_input = user_input
                self._rooms = []
                return await self.async_step_room_add()

        return self.async_show_form(step_id="user", data_schema=_user_schema(), errors=errors)

    async def async_step_room_add(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a single room selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                room = _parse_room(user_input[CONF_ROOMS])
            except vol.Invalid:
                errors[CONF_ROOMS] = "invalid_room"
            else:
                if room not in self._rooms:
                    self._rooms.append(room)
                return await self.async_step_room_menu()

        return self.async_show_form(
            step_id="room_add",
            data_schema=_rooms_schema(),
            errors=errors,
        )

    async def async_step_room_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Choose whether to add another room or finish."""
        return self.async_show_menu(
            step_id="room_menu",
            menu_options=["room_add", "finish"],
        )

    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Finish the flow."""
        return self.async_create_entry(
            title=f"{self._user_input[CONF_USERNAME]} @ {self._user_input[CONF_HOMESERVER]}",
            data={**self._user_input, CONF_ROOMS: list(self._rooms)},
        )

    async def async_step_import(
        self, import_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Import config from YAML if needed."""
        return await self.async_step_user(import_data)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return MatrixRoomsOptionsFlow()


class MatrixRoomsOptionsFlow(config_entries.OptionsFlowWithReload):
    """Handle options for Matrix Rooms."""

    def __init__(self) -> None:
        self._user_input: dict[str, Any] = {}
        self._rooms: list[str] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if not self._user_input:
            self._user_input = {**self.config_entry.data, **self.config_entry.options}
        if not self._rooms:
            self._rooms = list(self._user_input.get(CONF_ROOMS, []))

        if user_input is not None:
            self._user_input.update(user_input)
            return await self.async_step_room_add()

        return self.async_show_form(
            step_id="init",
            data_schema=_user_schema(self._user_input),
        )

    async def async_step_room_add(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add a single room."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                room = _parse_room(user_input[CONF_ROOMS])
            except vol.Invalid:
                errors[CONF_ROOMS] = "invalid_room"
            else:
                if room not in self._rooms:
                    self._rooms.append(room)
                return await self.async_step_room_menu()

        return self.async_show_form(
            step_id="room_add",
            data_schema=_rooms_schema(),
            errors=errors,
        )

    async def async_step_room_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Choose whether to add another room or finish."""
        return self.async_show_menu(
            step_id="room_menu",
            menu_options=["room_add", "finish"],
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Save options."""
        data = {**self._user_input, CONF_ROOMS: list(self._rooms)}
        return self.async_create_entry(title="", data=data)
