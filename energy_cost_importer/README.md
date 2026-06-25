# Energy Cost Importer

Imports calculated electricity cost statistics for Home Assistant Energy.

Supported built-in profiles:

- Haugaland Kraft Hyttekraft + Fagne + Norgespris
- Vibb + LNETT + Norgespris
- Custom numeric tariff

The app talks to Home Assistant through the Supervisor Core WebSocket proxy, so no long-lived access token is needed when installed as a Home Assistant app/add-on.

See `DOCS.md` for configuration.
