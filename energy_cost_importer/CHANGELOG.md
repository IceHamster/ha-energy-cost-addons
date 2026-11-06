# Changelog

## 0.2.5

- Apply Elvia's January–June and July–December 2026 energy and capacity prices automatically.
- Correct BKK/Eviny 2025 energy prices for January–March, April–August, September and October–December, and capacity prices before September.
- Fetch previous-month consumption for capacity calculations without importing costs or using quota for those extra rows.
- Refuse imports with missing or partial previous-month capacity history, preserving existing cost statistics.
- Remove the unverified LNETT capacity tier at and above 25 kW; require verified custom prices for usage outside published tiers.
- Restrict year-specific grid presets to their verified year and document official sources checked on 2026-11-06.
- Preserve manual energy and capacity overrides when applying historical defaults and dated supplier changes.
- Add offline regression tests for historical billing, capacity history, daylight-saving changes and import safety.

## 0.2.4

- Pin the Home Assistant base image to `3.24-2026.10.3`.
- Refresh Python and timezone data from the supported Alpine package repository during builds.
- Upgrade `websockets` to `17.4`, including its fragmented-message security fix.
- Run the importer from a dedicated Python virtual environment with pinned Python requirements.

## 0.2.3

- Add `capacity_daily_peak_days`, `capacity_daily_peak_timestamps` and `capacity_daily_peak_values_kw`.
- These attributes expose the daily maximum hourly consumption values that the monthly top-N capacity model uses.
- Enables fast dashboards without browser-side recorder history queries.

## 0.2.2

- Add `capacity_peak_timestamps` to the monthly cost sensor attributes.
- Keep `capacity_peak_days` and `capacity_peak_values_kw` unchanged for backward compatibility.
- Enables dashboards to place capacity peak markers at the exact hour that affected the capacity tier.

## 0.2.1

- Add official private grid tariff presets for Elvia 2026 and Eviny/BKK 2026.
- Add independent `grid_tariff_profile` so grid owner prices can be combined with any power supplier profile.
- Split Fagne and LNETT into independent grid tariff profiles while keeping old combined profiles backward compatible.
- Add seasonal grid energy rates through `grid_energy_rates_json`.
- Add Norwegian public-holiday handling for grid day/night energy tariffs.
- Add `capacity_basis_month_offset` for grid owners where the capacity tier is based on a previous month.

## 0.2.0

- Add data-driven `capacity_model_json` for grid owner capacity tariffs.
- Support `monthly_top_n_daily_peaks`, `monthly_max_hour`, `fixed_monthly` and `disabled` capacity models.
- Keep `grid_capacity_profile`, `grid_capacity_tiers_json` and `grid_capacity_monthly_nok` backward compatible.
- Add capacity dashboard attributes: current tier, next tier, margin to next tier, peak days, peak values and warning level.

## 0.1.7

- Add optional `tariff_periods_json` for dated tariff periods with `valid_from` and `valid_to`.
- Keep existing top-level tariff config fully backward compatible when no tariff periods are configured.
- Prorate monthly provider fixed cost and grid capacity cost when tariff periods change mid-month.
- Add generated add-on logo/icon assets.

## 0.1.6

- Add day, week and month cost breakdown attributes to sensor-based `monthly_cost_entity`.
- Add monthly tariff component attributes for dashboard breakdown cards.

## 0.1.5

- Allow `monthly_cost_entity` to be a non-editable `sensor.*` entity.
- Keep `input_number.*` support for existing installations.

## 0.1.4

- Add optional `monthly_cost_entity` for updating an `input_number` helper with current month cost.

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
