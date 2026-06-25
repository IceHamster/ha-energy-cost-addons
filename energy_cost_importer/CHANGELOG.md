# Changelog

## 0.1.3

- Start the Python process through `with-contenv` so Home Assistant app environment variables, including `SUPERVISOR_TOKEN`, are available.

## 0.1.2

- Make tariff detail options optional when using built-in profiles.
- Fill tariff defaults from the selected profile at runtime.
- Allow explicit options to override profile defaults.

## 0.1.1

- Use safe empty default entity IDs for generic installations.
- Refuse to start until required entity IDs are configured.
- Default `update_energy_dashboard` to `false` for new generic installs.

## 0.1.0

- Initial version.
- Imports calculated electricity cost statistics for the Energy dashboard.
- Supports provider/grid profiles, hourly updates and nightly rebuilds.
