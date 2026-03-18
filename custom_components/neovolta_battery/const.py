"""Constants for the NeoVolta Battery integration."""

DOMAIN = "neovolta_battery"

# Config entry keys
CONF_APPID = "appid"
CONF_SECRET = "secret"
CONF_USERNAME = "username"
CONF_PASSHASH = "passhash"
CONF_STATION_ID = "station_id"
CONF_INVERTER_SN = "inverter_sn"
CONF_INVERTER_ID = "inverter_id"
CONF_LOGGER_SN = "logger_sn"
CONF_LOGGER_ID = "logger_id"

# API
SOLARMAN_URL = "https://globalapi.solarmanpv.com"
DEFAULT_SCAN_INTERVAL = 300  # seconds

# Inverter fields that are static (do not change during operation).
# These are logged once at startup and excluded from sensor entities.
STATIC_FIELDS: frozenset[str] = frozenset({
    "Battery_Rated_Capacity",
    "Battery_Voltage_Type",
    "Discharge_Current_Limit",
    "General_Settings",
    "Grid_Type",
    "HMI",
    "Inverter_Type",
    "Lithium_Battery_Version_Number",
    "MAIN_1",
    "MAIN_2",
    "Protocol_Version",
    "Rated_Power",
})

# Inverter fields that duplicate data available elsewhere and should be
# dropped entirely from the returned data.
IGNORED_FIELDS: frozenset[str] = frozenset({
    "BMS_SOC",
    "SOC",
})
