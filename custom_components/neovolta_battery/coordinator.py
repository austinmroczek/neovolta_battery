"""DataUpdateCoordinator for NeoVolta Battery."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

LOGGER = logging.getLogger(__name__)


class NeoVoltaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls the Solarman API for NeoVolta battery data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._api = SolarmanApi(
            session=async_get_clientsession(hass),
            appid=entry.data[CONF_APPID],
            secret=entry.data[CONF_SECRET],
            username=entry.data[CONF_USERNAME],
            passhash=entry.data[CONF_PASSHASH],
        )
        # Restore discovered device identifiers
        self._api.station_id = entry.data.get(CONF_STATION_ID, 0)
        self._api.inverter_sn = entry.data.get(CONF_INVERTER_SN, "")
        self._api.inverter_id = entry.data.get(CONF_INVERTER_ID, 0)
        self._api.logger_sn = entry.data.get(CONF_LOGGER_SN, "")
        self._api.logger_id = entry.data.get(CONF_LOGGER_ID, 0)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Solarman API."""
        # Authenticate lazily (token is None on first call after restart)
        if not self._api.token:
            try:
                await self._api.authenticate()
            except SolarmanAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except SolarmanApiError as err:
                raise UpdateFailed(f"Cannot connect to Solarman API: {err}") from err

        try:
            return await self._fetch_data()
        except SolarmanAuthError:
            # Token expired — re-authenticate and retry once
            LOGGER.debug("Token expired, re-authenticating")
            try:
                await self._api.authenticate()
                return await self._fetch_data()
            except SolarmanAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except SolarmanApiError as err:
                raise UpdateFailed(f"Error after re-auth: {err}") from err
        except SolarmanApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def _fetch_data(self) -> dict[str, Any]:
        """Fetch all data from the API."""
        station_realtime = await self._api.get_station_realtime()

        inverter_data: dict[str, Any] = {}
        if self._api.inverter_sn:
            inverter_data = await self._api.get_device_current_data(
                self._api.inverter_sn, self._api.inverter_id
            )

        return {
            "station_realtime": station_realtime,
            "inverter_data": inverter_data,
        }
