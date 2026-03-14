# NeoVolta Battery — Home Assistant Integration

A custom Home Assistant integration that displays real-time data from a **NeoVolta NV14** home battery system via the [Solarman cloud API](https://globalapi.solarmanpv.com).

## Features

- Battery state of charge (%)
- Real-time power flows — battery, grid, load, and generation
- Daily energy totals — charge, discharge, grid purchase/sell, load
- All device-reported parameters from the NeoVolta inverter (voltage, current, temperature, frequency, etc.), dynamically discovered
- Automatic device discovery — no manual entry of serial numbers or station IDs
- Polls every 5 minutes; token refresh handled automatically

## Prerequisites

- Home Assistant 2024.1 or later
- A [Solarman developer account](https://home.solarmanpv.com) with an App ID and App Secret
- Your NeoVolta NV14 registered and visible in the Solarman app

## Installation

### HACS (recommended)

1. In Home Assistant, open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/austinmroczek/neovolta_battery` with category **Integration**.
3. Search for **NeoVolta Battery** and install it.
4. Restart Home Assistant.

### Manual

1. Copy the `custom_components/neovolta_battery/` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

1. Go to **Settings → Integrations → Add Integration**.
2. Search for **NeoVolta Battery**.
3. Enter your Solarman API credentials:

| Field | Description |
|---|---|
| App ID | Your Solarman developer App ID (15–16 characters) |
| App Secret | Your Solarman developer App Secret (32 characters) |
| Username | Email address used to log in to the Solarman app |
| Password | Your Solarman app password (stored as a SHA-256 hash) |

The integration will automatically discover your station, inverter, and data logger.

## Sensors

### Station

| Sensor | Unit | Description |
|---|---|---|
| Battery State of Charge | % | Current battery level |
| Battery Power | W | Net battery power (positive = charging, negative = discharging) |
| Charge Power | W | Battery charge rate |
| Discharge Power | W | Battery discharge rate |
| Grid Power | W | Net grid power (positive = importing, negative = exporting) |
| Load Power | W | Current home consumption |
| Generation Power | W | Current solar/generation output |
| Battery Charge Today | kWh | Energy charged into the battery today |
| Battery Discharge Today | kWh | Energy discharged from the battery today |
| Grid Purchase Today | kWh | Energy purchased from the grid today |
| Grid Sell Today | kWh | Energy sold to the grid today |
| Load Energy Today | kWh | Total home energy consumption today |
| Generation Today | kWh | Total generation today |
| Total Generation | kWh | Lifetime generation total |

### Inverter (dynamic)

Additional sensors are automatically created for every parameter the NeoVolta inverter reports — including voltage, current, temperature, frequency, and more. The exact set depends on what your device exposes via the Solarman API.

## Solarman API Credentials

To obtain an App ID and App Secret:

1. Log in to the [Solarman Developer Portal](https://home.solarmanpv.com).
2. Navigate to **API Management** and create a new application.
3. Copy the **App ID** and **App Secret** shown for your application.

## Contributing

Pull requests are welcome. Please open an issue first to discuss significant changes.

## License

[MIT](LICENSE)
