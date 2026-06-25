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
- `capacity_model_type`: capacity model used for the current month.
- `capacity_current_tier`: current capacity tier label.
- `capacity_next_tier`: next capacity tier label, if any.
- `capacity_margin_to_next_kw`: kW margin before the next capacity tier.
- `capacity_peak_days`, `capacity_peak_timestamps` and `capacity_peak_values_kw`: the peaks used by the capacity model. `capacity_peak_timestamps` contains the exact hour start for dashboard markers.
- `capacity_basis_month`: the month used as the basis for capacity tier calculation.
- `capacity_basis_incomplete`: `true` when the configured basis month has no imported consumption history.
- `capacity_warning_level`: `ok`, `near_next_tier`, `at_highest_tier`, `fixed` or `disabled`.

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

## Grid tariff profiles

Use `grid_tariff_profile` when the power supplier and the grid owner should be configured separately. This is preferred for new setups because the same supplier profile can be combined with different grid owners.

Current built-in grid tariff profiles:

- `fagne_2026_private`: Fagne private/cabin tariff defaults used by the legacy Hyttekraft + Fagne profile.
- `lnett_2026_private`: LNETT private tariff defaults used by the legacy Vibb + LNETT profile.
- `elvia_2026_private`: Elvia private tariff from 2026-07-01. Uses the official tariff sheet day/night energy prices and Elvia capacity steps.
- `eviny_bkk_2026_private`: Eviny/BKK private tariff from 2026-01-01. Uses BKK day/night energy prices and capacity steps.
- `bkk_2026_private`: same as `eviny_bkk_2026_private`, with the grid company name.

Historical aliases for dated tariff periods:

- `eviny_bkk_2025_private`
- `bkk_2025_private`

The grid day/night split treats weekdays 06:00-22:00 as day price. Evenings, nights, weekends and Norwegian public holidays use the night/weekend price.

BKK/Eviny calculates the capacity tier from the previous month. The add-on handles this with `capacity_basis_month_offset: -1` in the built-in model. If your `start_time` does not include the previous month, the first calculated month can show `capacity_basis_incomplete: true`.

Example with a custom supplier and Elvia grid:

```yaml
profile: custom
grid_tariff_profile: elvia_2026_private
provider_monthly_nok: 49
provider_markup_nok_per_kwh: 0
energy_entity: sensor.monthly_energy
spot_entity: sensor.nordpool
spot_price_unit: ore_per_kwh
spot_price_multiplier_to_nok_per_kwh: 0.01
cost_statistic_id: energy_cost_importer:elvia_total
monthly_cost_entity: sensor.power_cost_this_month
start_time: "2026-07-01T00:00:00+02:00"
timezone: Europe/Oslo
update_interval_minutes: 60
daily_rebuild_time: "03:17"
update_energy_dashboard: true
norgespris_enabled: true
norgespris_limit_kwh: 5000
norgespris_nok_per_kwh: 0.50
```

Example with a custom supplier and LNETT grid:

```yaml
profile: custom
grid_tariff_profile: lnett_2026_private
provider_monthly_nok: 49
provider_markup_nok_per_kwh: 0
energy_entity: sensor.monthly_energy
spot_entity: sensor.nordpool
spot_price_unit: ore_per_kwh
spot_price_multiplier_to_nok_per_kwh: 0.01
cost_statistic_id: energy_cost_importer:lnett_total
monthly_cost_entity: sensor.power_cost_this_month
start_time: "2026-01-01T00:00:00+01:00"
timezone: Europe/Oslo
update_interval_minutes: 60
daily_rebuild_time: "03:17"
update_energy_dashboard: true
norgespris_enabled: true
norgespris_limit_kwh: 5000
norgespris_nok_per_kwh: 0.50
```

Example with a custom supplier and Eviny/BKK grid:

```yaml
profile: custom
grid_tariff_profile: eviny_bkk_2026_private
provider_monthly_nok: 49
provider_markup_nok_per_kwh: 0
energy_entity: sensor.monthly_energy
spot_entity: sensor.nordpool
spot_price_unit: ore_per_kwh
spot_price_multiplier_to_nok_per_kwh: 0.01
cost_statistic_id: energy_cost_importer:eviny_bkk_total
monthly_cost_entity: sensor.power_cost_this_month
start_time: "2026-01-01T00:00:00+01:00"
timezone: Europe/Oslo
update_interval_minutes: 60
daily_rebuild_time: "03:17"
update_energy_dashboard: true
norgespris_enabled: true
norgespris_limit_kwh: 1000
norgespris_nok_per_kwh: 0.50
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
- A period can set its own `grid_tariff_profile`; grid tariff defaults are then applied before the period-specific overrides.
- Monthly provider fixed cost and grid capacity cost are prorated if a period starts or ends mid-month.
- Capacity model fields can be set inside each tariff period if the grid owner's steps or calculation method change.

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
      "grid_tariff_profile": "",
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

Profiles are convenience presets that may include both supplier and grid defaults. For new generic setups, use `profile: custom` plus `grid_tariff_profile` and explicit supplier fields.

For `custom`, set:

```yaml
provider_markup_nok_per_kwh: 0
provider_monthly_nok: 0
grid_day_nok_per_kwh: 0
grid_night_weekend_nok_per_kwh: 0
grid_energy_rates_json: "[]"
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

- `elvia_2026_private`
- `bkk_2026_private`
- `fagne_2026`
- `lnett_2026_private`
- `custom`

## Capacity models

Grid owners can have different capacity tariff steps and sometimes different calculation methods. The recommended generic configuration is `capacity_model_json`. It can be used at the top level or inside a tariff period.

The old options are still supported:

- `grid_capacity_profile`
- `grid_capacity_tiers_json`
- `grid_capacity_monthly_nok`

If `capacity_model_json` is set, it takes precedence over those old options.

### Monthly top N daily peaks

Use this for grid owners where the capacity tier is based on the average of the highest daily maximum hourly consumptions in the month. This covers the LNETT/Fagne-style model.

```yaml
capacity_model_json: >
  {
    "type": "monthly_top_n_daily_peaks",
    "peak_count": 3,
    "tiers": [
      {"label": "0-2 kW", "from_kw": 0, "to_kw": 2, "monthly_nok": 150},
      {"label": "2-5 kW", "from_kw": 2, "to_kw": 5, "monthly_nok": 250},
      {"label": "5-10 kW", "from_kw": 5, "to_kw": 10, "monthly_nok": 400},
      {"label": "10-15 kW", "from_kw": 10, "to_kw": 15, "monthly_nok": 650},
      {"label": "15-20 kW", "from_kw": 15, "to_kw": 20, "monthly_nok": 900},
      {"label": "20-25 kW", "from_kw": 20, "to_kw": 25, "monthly_nok": 1150},
      {"label": "over 25 kW", "from_kw": 25, "to_kw": null, "monthly_nok": 1150}
    ]
  }
```

For grid owners that use the previous month as the basis, add `capacity_basis_month_offset: -1`:

```yaml
capacity_model_json: >
  {
    "type": "monthly_top_n_daily_peaks",
    "peak_count": 3,
    "capacity_basis_month_offset": -1,
    "tiers": [
      {"label": "0-2 kW", "from_kw": 0, "to_kw": 2, "monthly_nok": 155},
      {"label": "2-5 kW", "from_kw": 2, "to_kw": 5, "monthly_nok": 250}
    ]
  }
```

### Monthly max hour

Use this for grid owners where the capacity tier is based on the single highest hourly consumption in the month.

```yaml
capacity_model_json: >
  {
    "type": "monthly_max_hour",
    "tiers": [
      {"label": "0-5 kW", "from_kw": 0, "to_kw": 5, "monthly_nok": 200},
      {"label": "5-10 kW", "from_kw": 5, "to_kw": 10, "monthly_nok": 350},
      {"label": "over 10 kW", "from_kw": 10, "to_kw": null, "monthly_nok": 600}
    ]
  }
```

### Fixed monthly capacity amount

Use this when the grid owner has a fixed monthly amount and no capacity tier calculation.

```yaml
capacity_model_json: >
  {
    "type": "fixed_monthly",
    "monthly_nok": 199
  }
```

### Disabled capacity calculation

Use this when capacity cost should not be included.

```yaml
capacity_model_json: >
  {
    "type": "disabled"
  }
```

### Best practice for grid owners

- Put the grid owner's steps in `capacity_model_json` instead of modifying Python code.
- Put `capacity_model_json` inside `tariff_periods_json` when steps change by date.
- Keep old tariff periods if `replace_on_start: true` is enabled.
- Use clear tier labels matching the grid owner's price list.
- Verify whether the grid owner uses top daily peaks, one monthly max hour, fixed amount or another model before configuring.
- Verify whether the capacity tier is based on the current month or a previous month.
- Do not assume all Norwegian grid owners use the LNETT/Fagne model.

Example inside a tariff period:

```yaml
tariff_periods_json: >
  [
    {
      "name": "Grid owner 2026",
      "valid_from": "2026-01-01T00:00:00+01:00",
      "valid_to": null,
      "profile": "custom",
      "provider_monthly_nok": 49,
      "grid_day_nok_per_kwh": 0.42,
      "grid_night_weekend_nok_per_kwh": 0.27,
      "capacity_model_json": {
        "type": "monthly_top_n_daily_peaks",
        "peak_count": 3,
        "tiers": [
          {"label": "0-5 kW", "from_kw": 0, "to_kw": 5, "monthly_nok": 200},
          {"label": "5-10 kW", "from_kw": 5, "to_kw": 10, "monthly_nok": 350}
        ]
      }
    }
  ]
```

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
