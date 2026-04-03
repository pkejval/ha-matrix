"""Config flow for Matrix Rooms."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import CONF_HOMESERVER, CONF_ROOMS, DOMAIN
from .util import normalize_room_ids


def _parse_rooms(value: str) -> list[str]:
    """Parse room ids or aliases from a text field."""
    rooms = normalize_room_ids(value)
    invalid = [room for room in rooms if not room.startswith(("!", "#"))]
    if invalid:
        raise vol.Invalid(
            "Rooms must be Matrix room ids or aliases starting with ! or #"
        )
    return rooms


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the base config schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOMESERVER, default=defaults.get(CONF_HOMESERVER, "")): cv.url,
            vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): cv.string,
            vol.Required(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): cv.string,
            vol.Optional(
                CONF_VERIFY_SSL,
                default=defaults.get(CONF_VERIFY_SSL, True),
            ): cv.boolean,
        }
    )


def _rooms_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the room list schema."""
    defaults = defaults or {}
    room_value = "\n".join(defaults.get(CONF_ROOMS, []))
    return vol.Schema(
        {
            vol.Optional(CONF_ROOMS, default=room_value): cv.string,
        }
    )


class MatrixRoomsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Matrix Rooms."""

    VERSION = 1

    def __init__(self) -> None:
        self._user_input: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOMESERVER]}|{user_input[CONF_USERNAME]}"
            )
            self._abort_if_unique_id_configured()
            self._user_input = user_input
            return await self.async_step_rooms()

        return self.async_show_form(step_id="user", data_schema=_user_schema(), errors=errors)

    async def async_step_rooms(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the room selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                rooms = _parse_rooms(user_input.get(CONF_ROOMS, ""))
            except vol.Invalid:
                errors[CONF_ROOMS] = "invalid_rooms"
            else:
                return self.async_create_entry(
                    title=f"{self._user_input[CONF_USERNAME]} @ {self._user_input[CONF_HOMESERVER]}",
                    data={**self._user_input, CONF_ROOMS: rooms},
                )

        return self.async_show_form(
            step_id="rooms",
            data_schema=_rooms_schema(self._user_input),
            errors=errors,
        )

    async def async_step_import(
        self, import_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Import config from YAML if needed."""
        return await self.async_step_user(import_data)


class MatrixRoomsOptionsFlow(config_entries.OptionsFlowWithReload):
    """Handle options for Matrix Rooms."""

    def __init__(self) -> None:
        self._user_input: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if not self._user_input:
            self._user_input = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            self._user_input.update(user_input)
            return await self.async_step_rooms()

        return self.async_show_form(
            step_id="init",
            data_schema=_user_schema(self._user_input),
        )

    async def async_step_rooms(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit rooms."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                rooms = _parse_rooms(user_input.get(CONF_ROOMS, ""))
            except vol.Invalid:
                errors[CONF_ROOMS] = "invalid_rooms"
            else:
                data = {**self._user_input, CONF_ROOMS: rooms}
                return self.async_create_entry(title="", data=data)

        return self.async_show_form(
            step_id="rooms",
            data_schema=_rooms_schema(self._user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return MatrixRoomsOptionsFlow()
