# Energy Cost Importer

Imports calculated electricity cost statistics for Home Assistant Energy.

Supported built-in profiles:

- Haugaland Kraft Hyttekraft + Fagne + Norgespris
- Vibb + LNETT + Norgespris
- Custom numeric tariff

Before starting the add-on, configure your energy sensor, spot price sensor, and optionally a `sensor.*` or `input_number.*` entity for current month cost. See `DOCS.md`.

Advanced users can configure dated tariff periods with `tariff_periods_json` so historical rebuilds keep the correct prices when supplier, grid or Norgespris settings change over time.

Grid owner capacity tariffs are data-driven through `capacity_model_json`. Built-in LNETT/Fagne profiles still work, but custom steps and calculation models can be configured without code changes.

The app talks to Home Assistant through the Supervisor Core WebSocket proxy, so no long-lived access token is needed when installed as a Home Assistant app/add-on.

See `DOCS.md` for configuration.
