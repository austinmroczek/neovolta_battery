"""Solarman API client for NeoVolta Battery integration.

Adapted from https://github.com/austinmroczek/solarman-mqtt
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import aiohttp

from .const import SOLARMAN_URL

LOGGER = logging.getLogger(__name__)


class SolarmanApiError(Exception):
    """Exception raised for general Solarman API errors."""


class SolarmanAuthError(SolarmanApiError):
    """Exception raised for authentication failures."""


class SolarmanApi:
    """Connect to the Solarman cloud API and retrieve device data."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        appid: str,
        secret: str,
        username: str,
        passhash: str,
    ) -> None:
        self._session = session
        self.appid = appid
        self.secret = secret
        self.username = username
        self.passhash = passhash

        self.token: str | None = None

        # Populated by discover_devices()
        self.station_id: int = 0
        self.inverter_sn: str = ""
        self.inverter_id: int = 0
        self.logger_sn: str = ""
        self.logger_id: int = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _make_request(
        self,
        url: str,
        headers: dict,
        data: dict,
        operation: str = "request",
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ) -> dict[str, Any] | None:
        """POST to *url* with retry/back-off and return the JSON response."""
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    delay = retry_delay * (2 ** (attempt - 1))
                    LOGGER.debug(
                        "Retrying %s (attempt %d/%d) after %.0fs",
                        operation,
                        attempt + 1,
                        max_retries + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)

                async with self._session.post(
                    url=url,
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    response.raise_for_status()
                    return await response.json()

            except asyncio.TimeoutError:
                LOGGER.warning("Timeout during %s (attempt %d)", operation, attempt + 1)
            except aiohttp.ClientConnectionError:
                LOGGER.warning("Connection error during %s (attempt %d)", operation, attempt + 1)
            except aiohttp.ClientResponseError as exc:
                if 400 <= exc.status < 500 and exc.status != 429:
                    raise SolarmanApiError(
                        f"HTTP {exc.status} error during {operation}"
                    ) from exc
                LOGGER.warning("HTTP %d during %s (attempt %d)", exc.status, operation, attempt + 1)
            except aiohttp.ClientError as exc:
                LOGGER.warning("Request error during %s (attempt %d): %s", operation, attempt + 1, exc)

        raise SolarmanApiError(f"Max retries exceeded for {operation}")

    def _auth_headers(self) -> dict:
        if not self.token:
            raise SolarmanAuthError("Not authenticated — call authenticate() first")
        return {
            "Content-Type": "application/json",
            "Authorization": f"bearer {self.token}",
        }

    def _check_response(self, response: dict, operation: str) -> None:
        """Raise appropriate exceptions for failed API responses."""
        if not response:
            raise SolarmanApiError(f"Empty response during {operation}")

        if response.get("success", False):
            return

        code = int(response.get("code") or 0)
        msg = response.get("msg", "unknown error")

        if code in (401, 2101002):
            raise SolarmanAuthError(f"Authentication error during {operation}: {msg}")

        if code == 3501004:
            raise SolarmanApiError(
                f"Device temporarily unreachable during {operation} — will retry next poll cycle"
            )

        raise SolarmanApiError(f"API error {code} during {operation}: {msg}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def authenticate(self) -> None:
        """Fetch a new access token. Raises SolarmanAuthError on failure."""
        LOGGER.debug("Authenticating with Solarman API")
        response = await self._make_request(
            url=f"{SOLARMAN_URL}/account/v1.0/token?appId={self.appid}&language=en",
            headers={"Content-Type": "application/json"},
            data={
                "appSecret": self.secret,
                "email": self.username,
                "password": self.passhash,
            },
            operation="authentication",
        )
        if not response or not response.get("success"):
            raise SolarmanAuthError(
                f"Authentication failed: {response.get('msg', 'unknown error') if response else 'no response'}"
            )
        self.token = response["access_token"]
        LOGGER.debug("Successfully authenticated")

    async def discover_devices(self) -> dict[str, Any]:
        """Auto-discover station ID, inverter, and logger serial numbers/IDs.

        Must call authenticate() before this method.

        Returns a dict with discovered identifiers that should be persisted
        in the config entry so they can be restored on restart.
        """
        # --- Station ---
        station_response = await self._make_request(
            url=f"{SOLARMAN_URL}/station/v1.0/list?language=en",
            headers=self._auth_headers(),
            data={"page": 1, "size": 50},
            operation="station list",
        )
        if station_response and station_response.get("stationList"):
            self.station_id = int(station_response["stationList"][0]["id"])
            LOGGER.debug("Discovered station_id: %s", self.station_id)

        # --- Devices ---
        device_response = await self._make_request(
            url=f"{SOLARMAN_URL}/station/v1.0/device",
            headers=self._auth_headers(),
            data={"stationId": self.station_id},
            operation="device list",
        )
        if device_response and device_response.get("deviceListItems"):
            for device in device_response["deviceListItems"]:
                device_type = device.get("deviceType", "")
                sn = device.get("deviceSn", "")
                device_id = int(device.get("deviceId", 0))

                if device_type == "INVERTER":
                    self.inverter_sn = sn
                    self.inverter_id = device_id
                    LOGGER.debug("Discovered inverter SN=%s ID=%s", sn, device_id)
                elif device_type == "COLLECTOR":
                    self.logger_sn = sn
                    self.logger_id = device_id
                    LOGGER.debug("Discovered logger SN=%s ID=%s", sn, device_id)

        return {
            "station_id": self.station_id,
            "inverter_sn": self.inverter_sn,
            "inverter_id": self.inverter_id,
            "logger_sn": self.logger_sn,
            "logger_id": self.logger_id,
        }

    async def get_station_realtime(self) -> dict[str, Any]:
        """Return station-level realtime data (battery SOC, power flows, etc.)."""
        response = await self._make_request(
            url=f"{SOLARMAN_URL}/station/v1.0/realTime?language=en",
            headers=self._auth_headers(),
            data={"stationId": self.station_id},
            operation="station realtime",
        )
        self._check_response(response, "station realtime")
        return response

    async def get_device_current_data(
        self, device_sn: str, device_id: int
    ) -> dict[str, Any]:
        """Return current data for a device separated into system and per-pack buckets.

        The raw API returns a ``dataList`` of ``{key, name, value}`` objects.
        Fields whose key contains ``BAP{N}`` (e.g. ``SOC_BAP1``, ``Vtr1_BAP1``)
        belong to battery pack N; all other fields are system-level.

        Returns::

            {
                "system": {"Field_Name": value, ...},
                "packs":  {1: {"Field_Name": value, ...}, 2: {...}, ...},
            }
        """
        payload: dict[str, Any] = {"deviceSn": device_sn}
        if device_id:
            payload["deviceId"] = device_id

        response = await self._make_request(
            url=f"{SOLARMAN_URL}/device/v1.0/currentData?language=en",
            headers=self._auth_headers(),
            data=payload,
            operation=f"device current data ({device_sn})",
        )
        self._check_response(response, f"device current data ({device_sn})")

        # Matches keys like "SOC_BAP1", "Vtr3_BAP3", "Warn_BAP15"
        _pack_key_re = re.compile(r"BAP(\d{1,2})", re.IGNORECASE)
        # Matches keys like "BAP_r_Ccg1", "BAP_r_Cdcg5", "BAP_r_Vcg3"
        # where BAP_ is a prefix and the pack number is a trailing digit
        _bap_prefix_re = re.compile(r"^BAP_.*?(\d{1,2})$", re.IGNORECASE)
        # Strips pack suffix from display names, handling typos
        # e.g. "- Battery Pack 1", "-Battert Pack 1", "-battey pack 6"
        _pack_name_suffix_re = re.compile(
            r"[-\s]+batt?er[ty]+\s+pack\s*\d+$", re.IGNORECASE
        )

        data_list = response.get("dataList", [])

        # First pass: parse MAC_NUM1 to find installed packs.
        # The value is comma-separated where parts[N-1] is the serial number
        # for pack N (1-based). An empty/whitespace entry means not installed.
        pack_sns: dict[int, str] = {}
        for item in data_list:
            if item.get("key") == "MAC_NUM1":
                parts = item.get("value", "").split(",")
                for pack_num, sn in enumerate(parts, start=1):
                    sn = sn.strip()
                    if sn and pack_num <= 15:
                        pack_sns[pack_num] = sn
                break

        # Pre-populate buckets for installed packs only
        packs: dict[int, dict[str, Any]] = {
            num: {"serial_number": sn, "fields": {}}
            for num, sn in pack_sns.items()
        }
        system: dict[str, Any] = {}

        # Second pass: route each field to system or the correct pack bucket.
        # Each entry is {"value": ..., "unit": ...} so consumers can use the
        # API-provided unit directly instead of guessing from the field name.
        for item in data_list:
            key = item.get("key", "")
            raw_name = item.get("name", "")
            value = item.get("value")
            unit = item.get("unit")

            if not raw_name:
                continue

            # Skip serial number / IMEI fields — captured structurally above
            name_lower = raw_name.lower()
            if "sn" in name_lower or "serial" in name_lower or key == "MAC_NUM1":
                continue

            entry = {"value": value, "unit": unit}

            pack_match = _pack_key_re.search(key) or _bap_prefix_re.match(key)
            if pack_match:
                pack_num = int(pack_match.group(1))
                if pack_num not in packs:
                    continue  # not in MAC_NUM1 → not installed, skip
                clean_name = _pack_name_suffix_re.sub("", raw_name).strip()
                field = (clean_name or raw_name).replace(" ", "_")
                packs[pack_num]["fields"][field] = entry
            else:
                system[raw_name.replace(" ", "_")] = entry

        return {"system": system, "packs": packs}
