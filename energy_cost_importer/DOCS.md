# Energy Cost Importer

## What it does

This app calculates an imported cost statistic for Home Assistant Energy. It is intended for tariffs where the real price is more complex than a single hourly price sensor.

- Optional monthly quota pricing, for example Norgespris.
- Consumption above the monthly quota can use an hourly spot sensor.
- Supplier markup and fixed monthly amount.
- Grid energy tariff and capacity tier.
- Optional dated tariff periods for historical price changes.

The app can also point the Energy dashboard to the calculated cost statistic.

The add-on must be configured before first start. The default options intentionally use empty entity IDs so a generic install cannot accidentally change your Energy dashboard.

If `monthly_cost_entity` points to an `input_number`, the add-on updates that helper with the current month cost after every import. This is useful for simple dashboard cards.

## What you need to create in Home Assistant

Before starting the add-on, Home Assistant must already have:

- An energy consumption sensor with long-term statistics, normally `state_class: total_increasing`, unit `kWh`, and `device_class: energy`.
- A spot price sensor with long-term statistics.
- Optional: a `sensor.*` entity name for current month cost. The add-on creates/updates this sensor state automatically.

Recommended current month cost sensor:

```yaml
monthly_cost_entity: sensor.hytte_stromkostnad_denne_maneden
```

The add-on creates/updates this sensor through the Home Assistant API. It is not editable from the UI, which is preferred for dashboard display.

When `monthly_cost_entity` is a `sensor.*`, the sensor state is the estimated total cost for the current month. The add-on also adds attributes for dashboard cards:

- `today_cost` and `today_kwh`: variable usage cost and consumption today.
- `week_cost` and `week_kwh`: variable usage cost and consumption this ISO week, Monday to Sunday.
- `month_cost` and `month_kwh`: estimated current month cost and consumption.
- `quota_left_kwh`, `norgespris_used_kwh`, `above_quota_kwh` and `spot_kwh`: quota status.
- `month_power_cost`, `month_grid_energy_cost`, `month_fixed_cost`, `month_capacity_cost`, `month_provider_fixed_cost` and `month_provider_markup_cost`: cost components.
- `tariff_periods`: active tariff period name(s) for the current month.

Recommended dashboard pattern:

- Main view: show current month cost, current month kWh and remaining quota.
- Details view: show today/week/month cards and the cost component breakdown.
- Energy dashboard: use the imported statistic for historical day/week/month views.

Legacy alternative:

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

This works, but it is editable by users. Prefer a `sensor.*` entity unless you specifically want manual override.

## Example: Haugaland Kraft Hyttekraft and Fagne

```yaml
profile: hyttekraft_fagne_hytte
energy_entity: sensor.hytte_sensor_power_energy
spot_entity: sensor.nordpool_kwh_no2_nok_1_10_025
spot_price_unit: ore_per_kwh
spot_price_multiplier_to_nok_per_kwh: 0.01
cost_statistic_id: energy_cost_importer:hytte_total
cost_source: energy_cost_importer
monthly_cost_entity: sensor.hytte_stromkostnad_denne_maneden
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
monthly_cost_entity: sensor.monthly_power_cost
start_time: "2026-01-01T00:00:00+01:00"
update_interval_minutes: 60
daily_rebuild_time: "03:17"
update_energy_dashboard: true
```

## Dated tariff periods

Most users can keep the simple top-level configuration above. If prices change over time, use `tariff_periods_json` in the add-on configuration. Do not put this in `configuration.yaml` or in Lovelace.

When `tariff_periods_json` is empty or omitted, the add-on behaves exactly like older versions: the top-level profile and tariff fields apply to the whole imported history.

When `tariff_periods_json` is configured, the add-on chooses the active tariff period for each hourly consumption row:

- `valid_from` is inclusive.
- `valid_to` is exclusive.
- `valid_to: null` means the period is open-ended.
- Periods must not overlap.
- Fields inside a period override the top-level config.
- A period can set its own `profile`; profile defaults are then applied before the period-specific overrides.
- Monthly provider fixed cost and grid capacity cost are prorated if a period starts or ends mid-month.

Example with one open-ended Vibb + LNETT period:

```yaml
profile: vibb_lnett_norgespris
energy_entity: sensor.energy_usage
spot_entity: sensor.nordpool
spot_price_unit: nok_per_kwh
spot_price_multiplier_to_nok_per_kwh: 1
cost_statistic_id: home_energy_cost:total_v2
cost_source: home_energy_cost
monthly_cost_entity: sensor.hjem_stromkostnad_denne_maneden
start_time: "2026-01-01T00:00:00+01:00"
timezone: Europe/Oslo
update_interval_minutes: 60
daily_rebuild_time: "03:17"
replace_on_start: true
update_energy_dashboard: true
tariff_periods_json: >
  [
    {
      "name": "Vibb + LNETT 2026",
      "valid_from": "2026-01-01T00:00:00+01:00",
      "valid_to": null,
      "profile": "vibb_lnett_norgespris",
      "norgespris_enabled": true,
      "norgespris_limit_kwh": 5000,
      "norgespris_nok_per_kwh": 0.50
    }
  ]
```

Example with a price change:

```yaml
tariff_periods_json: >
  [
    {
      "name": "Old tariff",
      "valid_from": "2026-01-01T00:00:00+01:00",
      "valid_to": "2026-07-01T00:00:00+02:00",
      "profile": "vibb_lnett_norgespris",
      "grid_day_nok_per_kwh": 0.4216,
      "grid_night_weekend_nok_per_kwh": 0.2716,
      "provider_monthly_nok": 49
    },
    {
      "name": "New tariff",
      "valid_from": "2026-07-01T00:00:00+02:00",
      "valid_to": null,
      "profile": "vibb_lnett_norgespris",
      "grid_day_nok_per_kwh": 0.4300,
      "grid_night_weekend_nok_per_kwh": 0.2800,
      "provider_monthly_nok": 49
    }
  ]
```

Best practice:

- Start new periods on the first day of a month when possible.
- Keep old periods in the config if you use `replace_on_start: true`, otherwise old history can be recalculated with only the current tariff.
- Use clear period names, for example `Vibb + LNETT 2026 H1`.
- Cover the full range from `start_time` if you want exact historical rebuilds.

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
