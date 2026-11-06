# Energy Cost Importer

Imports calculated electricity cost statistics for Home Assistant Energy.

Supported built-in profiles:

- Haugaland Kraft Hyttekraft + Fagne + Norgespris
- Vibb + LNETT + Norgespris
- Custom numeric tariff

Supported built-in grid tariff profiles:

- LNETT private 2026
- Fagne 2026
- Elvia private 2026
- Eviny/BKK private 2026

Elvia 2026 and BKK/Eviny 2025 presets select the correct historical energy and capacity prices by month. Year-specific presets are limited to their verified year; prices are maintained in add-on releases, not fetched automatically. Official grid tariff sources were last checked on 2026-11-06.

BKK/Eviny capacity calculations fetch the previous month's hourly consumption automatically. If that history is incomplete, the import stops before changing existing cost statistics. LNETT usage at or above 25 kW requires a verified custom capacity model.

Before starting the add-on, configure your energy sensor, spot price sensor, and optionally a `sensor.*` or `input_number.*` entity for current month cost. See `DOCS.md`.

Advanced users can configure dated tariff periods with `tariff_periods_json` so historical rebuilds keep the correct prices when supplier, grid or Norgespris settings change over time.

Grid owner tariffs can be selected independently with `grid_tariff_profile`, or configured manually with `grid_day_nok_per_kwh`, `grid_night_weekend_nok_per_kwh`, `grid_energy_rates_json` and `capacity_model_json`. Old combined supplier/grid profiles still work, but new setups can keep supplier and grid owner separate.

The app talks to Home Assistant through the Supervisor Core WebSocket proxy, so no long-lived access token is needed when installed as a Home Assistant app/add-on.

See `DOCS.md` for configuration.
