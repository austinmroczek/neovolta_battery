"""Sensor platform for NeoVolta Battery."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_INVERTER_SN, CONF_STATION_ID, DOMAIN
from .coordinator import NeoVoltaCoordinator

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Station-level sensors (from get_station_realtime response keys)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class StationSensorEntityDescription(SensorEntityDescription):
    """Extends SensorEntityDescription with a data key for station realtime."""
    data_key: str = ""


STATION_SENSOR_DESCRIPTIONS: tuple[StationSensorEntityDescription, ...] = (
    StationSensorEntityDescription(
        key="battery_soc",
        data_key="batterySoc",
        name="Battery State of Charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    StationSensorEntityDescription(
        key="battery_power",
        data_key="batteryPower",
        name="Battery Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    StationSensorEntityDescription(
        key="grid_power",
        data_key="gridPower",
        name="Grid Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    StationSensorEntityDescription(
        key="use_power",
        data_key="usePower",
        name="Load Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    StationSensorEntityDescription(
        key="generation_power",
        data_key="generationPower",
        name="Generation Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    StationSensorEntityDescription(
        key="charge_power",
        data_key="chargePower",
        name="Charge Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    StationSensorEntityDescription(
        key="discharge_power",
        data_key="dischargePower",
        name="Discharge Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    StationSensorEntityDescription(
        key="battery_charge_today",
        data_key="batteryChargeToday",
        name="Battery Charge Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    StationSensorEntityDescription(
        key="battery_discharge_today",
        data_key="batteryDischargeToday",
        name="Battery Discharge Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    StationSensorEntityDescription(
        key="generation_today",
        data_key="generationToday",
        name="Generation Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    StationSensorEntityDescription(
        key="generation_total",
        data_key="generationTotal",
        name="Total Generation",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    StationSensorEntityDescription(
        key="purchased_today",
        data_key="purchasedToday",
        name="Grid Purchase Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    StationSensorEntityDescription(
        key="grid_sell_today",
        data_key="gridSellToday",
        name="Grid Sell Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    StationSensorEntityDescription(
        key="use_today",
        data_key="useToday",
        name="Load Energy Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


# ---------------------------------------------------------------------------
# Helpers for dynamic inverter sensors
# ---------------------------------------------------------------------------

def _infer_sensor_metadata(
    name: str,
) -> tuple[SensorDeviceClass | None, str | None, SensorStateClass | None]:
    """Best-effort inference of device class, unit, and state class from name."""
    name_lower = name.lower()

    if "voltage" in name_lower or name_lower.endswith("_v"):
        return SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT, SensorStateClass.MEASUREMENT
    if "current" in name_lower or name_lower.endswith("_a"):
        return SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE, SensorStateClass.MEASUREMENT
    if "power" in name_lower or name_lower.endswith("_w"):
        return SensorDeviceClass.POWER, UnitOfPower.WATT, SensorStateClass.MEASUREMENT
    if "energy" in name_lower or "kwh" in name_lower:
        return SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, SensorStateClass.TOTAL_INCREASING
    if "temperature" in name_lower or "temp" in name_lower:
        return SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, SensorStateClass.MEASUREMENT
    if "frequency" in name_lower or "freq" in name_lower or name_lower.endswith("_hz"):
        return SensorDeviceClass.FREQUENCY, UnitOfFrequency.HERTZ, SensorStateClass.MEASUREMENT
    if "soc" in name_lower:
        return SensorDeviceClass.BATTERY, PERCENTAGE, SensorStateClass.MEASUREMENT

    return None, None, None


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NeoVolta Battery sensors from a config entry."""
    coordinator: NeoVoltaCoordinator = hass.data[DOMAIN][entry.entry_id]

    station_id = entry.data[CONF_STATION_ID]
    inverter_sn = entry.data.get(CONF_INVERTER_SN, "")

    entities: list[SensorEntity] = []

    # Station sensors — add only those whose data key exists in the response
    station_data: dict[str, Any] = coordinator.data.get("station_realtime", {})
    for description in STATION_SENSOR_DESCRIPTIONS:
        if description.data_key in station_data:
            entities.append(
                NeoVoltaStationSensor(coordinator, entry, description, station_id)
            )

    inverter_data: dict[str, Any] = coordinator.data.get("inverter_data", {})

    # System-level inverter sensors
    for field_name in inverter_data.get("system", {}):
        entities.append(
            NeoVoltaInverterSensor(coordinator, entry, field_name, inverter_sn)
        )

    # Per-pack sensors — one HA device per installed battery pack
    for pack_num, pack_data in inverter_data.get("packs", {}).items():
        pack_sn = pack_data["serial_number"]
        for field_name in pack_data["fields"]:
            entities.append(
                NeoVoltaBatteryPackSensor(
                    coordinator, entry, field_name, inverter_sn, pack_num, pack_sn
                )
            )

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Entity classes
# ---------------------------------------------------------------------------

class NeoVoltaStationSensor(
    CoordinatorEntity[NeoVoltaCoordinator], SensorEntity
):
    """A sensor representing a station-level metric from the Solarman API."""

    entity_description: StationSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NeoVoltaCoordinator,
        entry: ConfigEntry,
        description: StationSensorEntityDescription,
        station_id: int,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._station_id = station_id
        self._attr_unique_id = f"{station_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(station_id))},
            name="NeoVolta NV14",
            manufacturer="NeoVolta",
            model="NV14",
            model_id="NV14-US",
            serial_number=entry.data.get(CONF_INVERTER_SN) or None,
        )

    @property
    def native_value(self) -> Any:
        station_realtime = self.coordinator.data.get("station_realtime", {})
        return station_realtime.get(self.entity_description.data_key)


class NeoVoltaInverterSensor(
    CoordinatorEntity[NeoVoltaCoordinator], SensorEntity
):
    """A dynamically created sensor for a field in the inverter's current data."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NeoVoltaCoordinator,
        entry: ConfigEntry,
        field_name: str,
        inverter_sn: str,
    ) -> None:
        super().__init__(coordinator)
        self._field_name = field_name
        self._inverter_sn = inverter_sn

        self._attr_unique_id = f"{inverter_sn}_{field_name}"
        self._attr_name = field_name.replace("_", " ").title()

        device_class, unit, state_class = _infer_sensor_metadata(field_name)
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, inverter_sn)},
            name="NeoVolta NV14",
            manufacturer="NeoVolta",
            model="NV14",
            model_id="NV14-US",
            serial_number=inverter_sn or None,
        )

    @property
    def native_value(self) -> Any:
        system = self.coordinator.data.get("inverter_data", {}).get("system", {})
        return system.get(self._field_name)


class NeoVoltaBatteryPackSensor(
    CoordinatorEntity[NeoVoltaCoordinator], SensorEntity
):
    """A dynamically created sensor for a single battery pack."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NeoVoltaCoordinator,
        entry: ConfigEntry,
        field_name: str,
        inverter_sn: str,
        pack_num: int,
        pack_sn: str,
    ) -> None:
        super().__init__(coordinator)
        self._field_name = field_name
        self._inverter_sn = inverter_sn
        self._pack_num = pack_num

        self._attr_unique_id = f"{inverter_sn}_pack{pack_num}_{field_name}"
        self._attr_name = field_name.replace("_", " ").title()

        device_class, unit, state_class = _infer_sensor_metadata(field_name)
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{inverter_sn}_pack{pack_num}")},
            name=f"Battery Pack {pack_num}",
            manufacturer="NeoVolta",
            model="NV14",
            serial_number=pack_sn,
            via_device=(DOMAIN, inverter_sn),
        )

    @property
    def native_value(self) -> Any:
        packs = self.coordinator.data.get("inverter_data", {}).get("packs", {})
        return packs.get(self._pack_num, {}).get("fields", {}).get(self._field_name)
