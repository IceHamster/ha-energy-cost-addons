# Energy Cost Importer

Imports calculated electricity cost statistics for Home Assistant Energy.

Supported built-in profiles:

- Haugaland Kraft Hyttekraft + Fagne + Norgespris
- Vibb + LNETT + Norgespris
- Custom numeric tariff

Before starting the add-on, configure your energy sensor, spot price sensor, and optionally an `input_number` helper for current month cost. See `DOCS.md`.

The app talks to Home Assistant through the Supervisor Core WebSocket proxy, so no long-lived access token is needed when installed as a Home Assistant app/add-on.

See `DOCS.md` for configuration.
