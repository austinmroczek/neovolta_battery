"""Config flow for the NeoVolta Battery integration."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SolarmanApi, SolarmanApiError, SolarmanAuthError
from .const import (
    CONF_APPID,
    CONF_INVERTER_ID,
    CONF_INVERTER_SN,
    CONF_LOGGER_ID,
    CONF_LOGGER_SN,
    CONF_PASSHASH,
    CONF_SECRET,
    CONF_STATION_ID,
    CONF_USERNAME,
    DOMAIN,
)

LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_APPID): str,
        vol.Required(CONF_SECRET): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required("password"): str,
    }
)


class NeoVoltaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NeoVolta Battery."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            passhash = hashlib.sha256(
                user_input["password"].encode("utf-8")
            ).hexdigest()

            api = SolarmanApi(
                session=async_get_clientsession(self.hass),
                appid=user_input[CONF_APPID],
                secret=user_input[CONF_SECRET],
                username=user_input[CONF_USERNAME],
                passhash=passhash,
            )

            try:
                await api.authenticate()
                discovered = await api.discover_devices()
            except SolarmanAuthError:
                errors["base"] = "invalid_auth"
            except SolarmanApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(str(discovered["station_id"]))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="NeoVolta Battery",
                    data={
                        CONF_APPID: user_input[CONF_APPID],
                        CONF_SECRET: user_input[CONF_SECRET],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSHASH: passhash,
                        CONF_STATION_ID: discovered["station_id"],
                        CONF_INVERTER_SN: discovered["inverter_sn"],
                        CONF_INVERTER_ID: discovered["inverter_id"],
                        CONF_LOGGER_SN: discovered["logger_sn"],
                        CONF_LOGGER_ID: discovered["logger_id"],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

