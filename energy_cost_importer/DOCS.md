# Energy Cost Importer

## What it does

This app calculates an imported cost statistic for Home Assistant Energy. It is intended for tariffs where the real price is more complex than a single hourly price sensor.

- Optional monthly quota pricing, for example Norgespris.
- Consumption above the monthly quota can use an hourly spot sensor.
- Supplier markup and fixed monthly amount.
- Grid energy tariff and capacity tier.

The app can also point the Energy dashboard to the calculated cost statistic.

The add-on must be configured before first start. The default options intentionally use empty entity IDs so a generic install cannot accidentally change your Energy dashboard.

If `monthly_cost_entity` points to an `input_number`, the add-on updates that helper with the current month cost after every import. This is useful for simple dashboard cards.

## What you need to create in Home Assistant

Before starting the add-on, Home Assistant must already have:

- An energy consumption sensor with long-term statistics, normally `state_class: total_increasing`, unit `kWh`, and `device_class: energy`.
- A spot price sensor with long-term statistics.
- Optional: an `input_number` helper if you want the add-on to expose current month cost as a normal dashboard entity.

Recommended helper for current month cost:

1. Go to Settings -> Devices & services -> Helpers.
2. Create helper -> Number.
3. Name: `Hytte strøm kostnad denne måneden` or `Power cost this month`.
4. Minimum: `0`.
5. Maximum: for example `100000`.
6. Step: `1`.
7. Display mode: `Input field`.
8. Unit of measurement: `kr` or your local currency.
9. Icon: `mdi:cash`.

Use the created helper entity as `monthly_cost_entity`, for example:

```yaml
monthly_cost_entity: input_number.hytte_strom_kostnad_denne_maneden
```

You can then show that helper on a normal dashboard card. The add-on writes the rounded current-month cost into the helper after each import.

## Example: Haugaland Kraft Hyttekraft and Fagne

```yaml
profile: hyttekraft_fagne_hytte
energy_entity: sensor.hytte_sensor_power_energy
spot_entity: sensor.nordpool_kwh_no2_nok_1_10_025
spot_price_unit: ore_per_kwh
spot_price_multiplier_to_nok_per_kwh: 0.01
cost_statistic_id: energy_cost_importer:hytte_total
cost_source: energy_cost_importer
monthly_cost_entity: input_number.hytte_strom_kostnad_denne_maneden
start_time: "2026-01-01T00:00:00+01:00"
timezone: Europe/Oslo
update_interval_minutes: 60
daily_rebuild_time: "03:17"
replace_on_start: false
update_energy_dashboard: true
norgespris_enabled: true
norgespris_limit_kwh: 1000
norgespris_nok_per_kwh: 0.50
```

## Example: Vibb and LNETT

```yaml
profile: vibb_lnett_norgespris
energy_entity: sensor.monthly_energy
spot_entity: sensor.nordpool
spot_price_unit: ore_per_kwh
spot_price_multiplier_to_nok_per_kwh: 0.01
cost_statistic_id: energy_cost_importer:vibb_lnett_total
monthly_cost_entity: input_number.monthly_power_cost
start_time: "2026-01-01T00:00:00+01:00"
update_interval_minutes: 60
daily_rebuild_time: "03:17"
update_energy_dashboard: true
```

## Spot price units

The app stores all costs in NOK/kWh internally. Configure `spot_price_multiplier_to_nok_per_kwh` to match your spot sensor:

- `ore_per_kwh`: use `0.01`
- `nok_per_kwh`: use `1`
- `nok_per_mwh`: use `0.001`
- other currency/MWh sensors: set a custom multiplier that converts one sensor unit to NOK/kWh

`spot_price_unit` is descriptive and kept in the options for readability. The multiplier controls the calculation.

## Profiles

Supported profiles:

- `hyttekraft_fagne_hytte`: Haugaland Kraft Hyttekraft, Fagne nettleie and Norgespris for cabin.
- `vibb_lnett_norgespris`: Vibb Spot, LNETT private grid tariff and Norgespris.
- `custom`: use the numeric options directly.

For `custom`, set:

```yaml
provider_markup_nok_per_kwh: 0
provider_monthly_nok: 0
grid_day_nok_per_kwh: 0
grid_night_weekend_nok_per_kwh: 0
grid_capacity_profile: custom
grid_capacity_monthly_nok: 0
grid_capacity_tiers_json: "[]"
norgespris_enabled: true
```

For custom capacity tiers, use JSON:

```yaml
grid_capacity_profile: custom
grid_capacity_tiers_json: '[[0,2,150],[2,5,250],[5,10,400],[10,15,650],[15,20,900],[20,25,1150],[25,null,1150]]'
```

Built-in grid capacity profiles:

- `fagne_2026`
- `lnett_2026_private`
- `custom`

## Installation

Local testing on a real Home Assistant OS/Supervised instance:

1. Install the Samba or SSH app.
2. Copy the `energy_cost_importer` folder to `/addons/energy_cost_importer`.
3. Go to Settings -> Add-ons -> Add-on Store.
4. Open the three-dot menu and select Reload.
5. Install `Energy Cost Importer`.

Repository installation:

1. Publish the parent folder as a Git repository with `repository.yaml` at the root.
2. Add that repository URL in the Home Assistant Add-on Store.
3. Install `Energy Cost Importer`.

## Why nightly rebuild exists

Many grid capacity tariffs are based on monthly peak hours. That means earlier cost rows for the current month may need recalculation later in the month. The hourly run keeps the Energy dashboard current. The nightly rebuild corrects the full imported statistic.

The same applies to LNETT, where the monthly capacity tier is based on the average of the three highest daily maximum hourly consumptions in a month.

## Sources

- Vibb price list: Vibb Spot is listed with 49 NOK monthly fixed amount and 0 ore/kWh markup.
- LNETT private grid tariff 2026: capacity tiers, day/night energy tariff, consumption tax and Enova fee.
- Fagne private grid tariff 2026: capacity tiers and day/night energy tariff.
- Haugaland Kraft Hyttekraft: spot agreement with markup and monthly fixed amount.
