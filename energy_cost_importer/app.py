import asyncio
import json
import os
from copy import deepcopy
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib import request
from zoneinfo import ZoneInfo

import websockets


OPTIONS_PATH = Path("/data/options.json")
REPORT_PATH = Path("/data/last_report.json")
CORE_WS_URL = "ws://supervisor/core/websocket"
CORE_API_URL = "http://supervisor/core/api"
INTERNAL_TARIFF_PERIODS = "_tariff_periods"
INTERNAL_CAPACITY_MODEL = "_capacity_model"


PROFILE_DEFAULTS = {
    "hyttekraft_fagne_hytte": {
        "provider_markup_nok_per_kwh": 0.0225,
        "provider_monthly_nok": 19.0,
        "grid_tariff_profile": "fagne_2026_private",
        "grid_day_nok_per_kwh": 0.4516,
        "grid_night_weekend_nok_per_kwh": 0.3516,
        "grid_capacity_profile": "fagne_2026",
        "norgespris_enabled": True,
    },
    "vibb_lnett_norgespris": {
        "provider_markup_nok_per_kwh": 0.0,
        "provider_monthly_nok": 49.0,
        "grid_tariff_profile": "lnett_2026_private",
        "grid_day_nok_per_kwh": 0.4216,
        "grid_night_weekend_nok_per_kwh": 0.2716,
        "grid_capacity_profile": "lnett_2026_private",
        "norgespris_enabled": True,
    },
}


BASE_TARIFF_DEFAULTS = {
    "norgespris_enabled": False,
    "norgespris_limit_kwh": 0.0,
    "norgespris_nok_per_kwh": 0.0,
    "provider_markup_nok_per_kwh": 0.0,
    "provider_monthly_nok": 0.0,
    "grid_tariff_profile": "",
    "grid_day_nok_per_kwh": 0.0,
    "grid_night_weekend_nok_per_kwh": 0.0,
    "grid_energy_rates_json": "[]",
    "grid_capacity_profile": "custom",
    "grid_capacity_monthly_nok": 0.0,
    "grid_capacity_tiers_json": "[]",
    "capacity_model_json": "{}",
    "capacity_warning_margin_kw": 0.5,
    "tariff_periods_json": "[]",
}


BUILTIN_CAPACITY_MODELS = {
    "fagne_2026": {
        "type": "monthly_top_n_daily_peaks",
        "peak_count": 3,
        "tiers": [
            {"label": "0-5 kW", "from_kw": 0, "to_kw": 5, "monthly_nok": 360.0},
            {"label": "5-10 kW", "from_kw": 5, "to_kw": 10, "monthly_nok": 460.0},
            {"label": "10-15 kW", "from_kw": 10, "to_kw": 15, "monthly_nok": 560.0},
            {"label": "15-20 kW", "from_kw": 15, "to_kw": 20, "monthly_nok": 660.0},
            {"label": "20-25 kW", "from_kw": 20, "to_kw": 25, "monthly_nok": 760.0},
            {"label": "25-50 kW", "from_kw": 25, "to_kw": 50, "monthly_nok": 2200.0},
            {"label": "50-75 kW", "from_kw": 50, "to_kw": 75, "monthly_nok": 3200.0},
            {"label": "75-100 kW", "from_kw": 75, "to_kw": 100, "monthly_nok": 4200.0},
            {"label": "over 100 kW", "from_kw": 100, "to_kw": None, "monthly_nok": 5200.0},
        ],
    },
    "lnett_2026_private": {
        "type": "monthly_top_n_daily_peaks",
        "peak_count": 3,
        "tiers": [
            {"label": "0-2 kW", "from_kw": 0, "to_kw": 2, "monthly_nok": 150.0},
            {"label": "2-5 kW", "from_kw": 2, "to_kw": 5, "monthly_nok": 250.0},
            {"label": "5-10 kW", "from_kw": 5, "to_kw": 10, "monthly_nok": 400.0},
            {"label": "10-15 kW", "from_kw": 10, "to_kw": 15, "monthly_nok": 650.0},
            {"label": "15-20 kW", "from_kw": 15, "to_kw": 20, "monthly_nok": 900.0},
            {"label": "20-25 kW", "from_kw": 20, "to_kw": 25, "monthly_nok": 1150.0},
            {"label": "over 25 kW", "from_kw": 25, "to_kw": None, "monthly_nok": 1150.0},
        ],
    },
    "elvia_2026_private": {
        "type": "monthly_top_n_daily_peaks",
        "peak_count": 3,
        "tiers": [
            {"label": "0-2 kW", "from_kw": 0, "to_kw": 2, "monthly_nok": 150.0},
            {"label": "2-5 kW", "from_kw": 2, "to_kw": 5, "monthly_nok": 250.0},
            {"label": "5-10 kW", "from_kw": 5, "to_kw": 10, "monthly_nok": 420.0},
            {"label": "10-15 kW", "from_kw": 10, "to_kw": 15, "monthly_nok": 585.0},
            {"label": "15-20 kW", "from_kw": 15, "to_kw": 20, "monthly_nok": 755.0},
            {"label": "20-25 kW", "from_kw": 20, "to_kw": 25, "monthly_nok": 925.0},
            {"label": "25-50 kW", "from_kw": 25, "to_kw": 50, "monthly_nok": 1760.0},
            {"label": "50-75 kW", "from_kw": 50, "to_kw": 75, "monthly_nok": 2600.0},
            {"label": "75-100 kW", "from_kw": 75, "to_kw": 100, "monthly_nok": 3440.0},
            {"label": "over 100 kW", "from_kw": 100, "to_kw": None, "monthly_nok": 6800.0},
        ],
    },
    "bkk_2026_private": {
        "type": "monthly_top_n_daily_peaks",
        "peak_count": 3,
        "capacity_basis_month_offset": -1,
        "tiers": [
            {"label": "0-2 kW", "from_kw": 0, "to_kw": 2, "monthly_nok": 155.0},
            {"label": "2-5 kW", "from_kw": 2, "to_kw": 5, "monthly_nok": 250.0},
            {"label": "5-10 kW", "from_kw": 5, "to_kw": 10, "monthly_nok": 415.0},
            {"label": "10-15 kW", "from_kw": 10, "to_kw": 15, "monthly_nok": 600.0},
            {"label": "15-20 kW", "from_kw": 15, "to_kw": 20, "monthly_nok": 770.0},
            {"label": "20-25 kW", "from_kw": 20, "to_kw": 25, "monthly_nok": 940.0},
            {"label": "25-50 kW", "from_kw": 25, "to_kw": 50, "monthly_nok": 1800.0},
            {"label": "50-75 kW", "from_kw": 50, "to_kw": 75, "monthly_nok": 2650.0},
            {"label": "75-100 kW", "from_kw": 75, "to_kw": 100, "monthly_nok": 3500.0},
            {"label": "over 100 kW", "from_kw": 100, "to_kw": None, "monthly_nok": 6900.0},
        ],
    },
}


GRID_TARIFF_DEFAULTS = {
    "fagne_2026_private": {
        "grid_day_nok_per_kwh": 0.4516,
        "grid_night_weekend_nok_per_kwh": 0.3516,
        "grid_energy_rates_json": "[]",
        "grid_capacity_profile": "fagne_2026",
    },
    "lnett_2026_private": {
        "grid_day_nok_per_kwh": 0.4216,
        "grid_night_weekend_nok_per_kwh": 0.2716,
        "grid_energy_rates_json": "[]",
        "grid_capacity_profile": "lnett_2026_private",
    },
    "elvia_2026_private": {
        "grid_day_nok_per_kwh": 0.4640,
        "grid_night_weekend_nok_per_kwh": 0.3140,
        "grid_energy_rates_json": "[]",
        "grid_capacity_profile": "elvia_2026_private",
    },
    "bkk_2026_private": {
        "grid_day_nok_per_kwh": 0.4613,
        "grid_night_weekend_nok_per_kwh": 0.2329,
        "grid_energy_rates_json": "[]",
        "grid_capacity_profile": "bkk_2026_private",
    },
    "eviny_bkk_2026_private": {
        "grid_day_nok_per_kwh": 0.4613,
        "grid_night_weekend_nok_per_kwh": 0.2329,
        "grid_energy_rates_json": "[]",
        "grid_capacity_profile": "bkk_2026_private",
    },
    "bkk_2025_private": {
        "grid_day_nok_per_kwh": 0.5287,
        "grid_night_weekend_nok_per_kwh": 0.4065,
        "grid_energy_rates_json": [
            {"months": [10, 11, 12], "grid_day_nok_per_kwh": 0.5287, "grid_night_weekend_nok_per_kwh": 0.4065},
        ],
        "grid_capacity_profile": "bkk_2026_private",
    },
    "eviny_bkk_2025_private": {
        "grid_day_nok_per_kwh": 0.5287,
        "grid_night_weekend_nok_per_kwh": 0.4065,
        "grid_energy_rates_json": [
            {"months": [10, 11, 12], "grid_day_nok_per_kwh": 0.5287, "grid_night_weekend_nok_per_kwh": 0.4065},
        ],
        "grid_capacity_profile": "bkk_2026_private",
    },
}


def log(message: str) -> None:
    print(f"[energy-cost-importer] {message}", flush=True)


def profile_defaults(profile: str) -> dict:
    if profile == "custom":
        return {}
    if profile not in PROFILE_DEFAULTS:
        raise ValueError(
            f"Unknown profile '{profile}'. Use one of: "
            f"{', '.join(sorted(PROFILE_DEFAULTS))}, custom"
        )
    return PROFILE_DEFAULTS[profile]


def grid_tariff_defaults(profile: str) -> dict:
    if profile in (None, "", "custom"):
        return {}
    if profile not in GRID_TARIFF_DEFAULTS:
        raise ValueError(
            f"Unknown grid_tariff_profile '{profile}'. Use one of: "
            f"{', '.join(sorted(GRID_TARIFF_DEFAULTS))}, custom"
        )
    return deepcopy(GRID_TARIFF_DEFAULTS[profile])


def resolve_options(raw_options: dict) -> dict:
    profile = raw_options.get("profile", "custom")
    options = {**BASE_TARIFF_DEFAULTS, **profile_defaults(profile)}
    grid_profile = raw_options.get("grid_tariff_profile", options.get("grid_tariff_profile", ""))
    grid_defaults = grid_tariff_defaults(grid_profile)
    options.update(grid_defaults)
    raw_overrides = {**raw_options}
    if (
        grid_profile not in (None, "", "custom")
        and raw_overrides.get("grid_energy_rates_json") in (None, "", BASE_TARIFF_DEFAULTS["grid_energy_rates_json"])
        and grid_defaults.get("grid_energy_rates_json") not in (None, "", BASE_TARIFF_DEFAULTS["grid_energy_rates_json"])
    ):
        raw_overrides.pop("grid_energy_rates_json", None)
    options.update(raw_overrides)
    return options


def load_options() -> dict:
    with OPTIONS_PATH.open() as handle:
        raw_options = json.load(handle)
    options = resolve_options(raw_options)
    validate_capacity_profile(options)
    options[INTERNAL_TARIFF_PERIODS] = build_tariff_periods(raw_options, options)
    validate_options(options)
    return options


def validate_capacity_profile(options: dict) -> None:
    build_capacity_model(options)


def validate_options(options: dict) -> None:
    required_entities = ["energy_entity", "spot_entity"]
    for key in required_entities:
        value = str(options.get(key, "")).strip()
        if not value:
            raise ValueError(f"{key} must be configured before starting the add-on")
        if not value.startswith("sensor."):
            raise ValueError(f"{key} must be a sensor entity_id, got {value!r}")
    statistic_id = str(options.get("cost_statistic_id", "")).strip()
    if ":" not in statistic_id:
        raise ValueError("cost_statistic_id must be an external statistic id, for example energy_cost_importer:total")
    monthly_cost_entity = str(options.get("monthly_cost_entity", "")).strip()
    if monthly_cost_entity and not monthly_cost_entity.startswith(("sensor.", "input_number.")):
        raise ValueError("monthly_cost_entity must be a sensor.* or input_number.* entity_id")


def parse_datetime(value, tz: ZoneInfo, field: str) -> datetime | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO datetime string or null")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as err:
        raise ValueError(f"{field} must be an ISO datetime string, got {value!r}") from err
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def parse_json_option(value, default, field: str):
    if value in (None, ""):
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as err:
            raise ValueError(f"{field} must contain valid JSON") from err
    return value


def build_period_options(period: dict, base_options: dict) -> dict:
    options = {**base_options}
    if "profile" in period:
        profile = period.get("profile", "custom")
        options.update(BASE_TARIFF_DEFAULTS)
        options.update(profile_defaults(profile))
    grid_profile = period.get("grid_tariff_profile", options.get("grid_tariff_profile", ""))
    options.update(grid_tariff_defaults(grid_profile))
    options.update(period)
    options.pop(INTERNAL_CAPACITY_MODEL, None)
    validate_capacity_profile(options)
    return options


def build_tariff_periods(raw_options: dict, base_options: dict) -> list[dict]:
    raw_periods = raw_options.get("tariff_periods_json", base_options.get("tariff_periods_json", "[]"))
    if isinstance(raw_periods, str):
        raw_periods = raw_periods.strip()
    if raw_periods in (None, "", "[]"):
        return []
    if isinstance(raw_periods, str):
        try:
            periods = json.loads(raw_periods)
        except json.JSONDecodeError as err:
            raise ValueError("tariff_periods_json must contain valid JSON") from err
    else:
        periods = raw_periods
    if not isinstance(periods, list):
        raise ValueError("tariff_periods_json must be a JSON list")

    tz = ZoneInfo(base_options["timezone"])
    normalized = []
    for index, period in enumerate(periods):
        if not isinstance(period, dict):
            raise ValueError(f"tariff_periods_json[{index}] must be an object")
        valid_from = parse_datetime(period.get("valid_from"), tz, f"tariff_periods_json[{index}].valid_from")
        valid_to = parse_datetime(period.get("valid_to"), tz, f"tariff_periods_json[{index}].valid_to")
        if valid_from and valid_to and valid_to <= valid_from:
            raise ValueError(f"tariff_periods_json[{index}].valid_to must be after valid_from")
        period_options = build_period_options(period, base_options)
        normalized.append(
            {
                "name": str(period.get("name") or period_options.get("profile") or f"tariff {index + 1}"),
                "valid_from": valid_from,
                "valid_to": valid_to,
                "options": period_options,
            }
        )

    start_floor = datetime.min.replace(tzinfo=tz)
    end_ceiling = datetime.max.replace(tzinfo=tz)
    normalized.sort(key=lambda item: item["valid_from"] or start_floor)
    previous_end = None
    for period in normalized:
        start = period["valid_from"] or start_floor
        end = period["valid_to"] or end_ceiling
        if previous_end and start < previous_end:
            raise ValueError("tariff_periods_json contains overlapping periods")
        previous_end = end
    return normalized


def month_key(dt: datetime, tz: ZoneInfo) -> str:
    return dt.astimezone(tz).strftime("%Y-%m")


def week_key(dt: datetime, tz: ZoneInfo) -> str:
    local = dt.astimezone(tz)
    year, week, _ = local.isocalendar()
    return f"{year}-W{week:02d}"


def day_key(dt: datetime, tz: ZoneInfo) -> str:
    return dt.astimezone(tz).strftime("%Y-%m-%d")


def month_bounds(key: str, tz: ZoneInfo) -> tuple[datetime, datetime]:
    year, month = [int(part) for part in key.split("-", 1)]
    start = datetime(year, month, 1, tzinfo=tz)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end = datetime(year, month + 1, 1, tzinfo=tz)
    return start, end


def shift_month_key(key: str, offset: int, tz: ZoneInfo) -> str:
    if offset == 0:
        return key
    year, month = [int(part) for part in key.split("-", 1)]
    month_index = year * 12 + (month - 1) + int(offset)
    shifted_year, shifted_month_index = divmod(month_index, 12)
    return datetime(shifted_year, shifted_month_index + 1, 1, tzinfo=tz).strftime("%Y-%m")


def empty_cost_summary() -> dict:
    return {
        "kwh": 0.0,
        "quota_kwh": 0.0,
        "spot_kwh": 0.0,
        "power_cost": 0.0,
        "provider_markup": 0.0,
        "grid_energy": 0.0,
        "fixed": 0.0,
        "variable_total": 0.0,
        "total": 0.0,
    }


def add_variable_cost(
    summary: dict,
    kwh: float,
    quota_kwh: float,
    spot_kwh: float,
    power_cost: float,
    markup_cost: float,
    grid_cost: float,
) -> None:
    variable_cost = power_cost + markup_cost + grid_cost
    summary["kwh"] += kwh
    summary["quota_kwh"] += quota_kwh
    summary["spot_kwh"] += spot_kwh
    summary["power_cost"] += power_cost
    summary["provider_markup"] += markup_cost
    summary["grid_energy"] += grid_cost
    summary["variable_total"] += variable_cost
    summary["total"] += variable_cost


def norway_easter(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def is_norwegian_public_holiday(day: date) -> bool:
    fixed_holidays = {(1, 1), (5, 1), (5, 17), (12, 25), (12, 26)}
    if (day.month, day.day) in fixed_holidays:
        return True
    easter = norway_easter(day.year)
    movable_holidays = {
        easter - timedelta(days=3),
        easter - timedelta(days=2),
        easter,
        easter + timedelta(days=1),
        easter + timedelta(days=39),
        easter + timedelta(days=49),
        easter + timedelta(days=50),
    }
    return day in movable_holidays


def grid_energy_rates(options: dict) -> list[dict]:
    rates = parse_json_option(options.get("grid_energy_rates_json", "[]"), [], "grid_energy_rates_json")
    if not isinstance(rates, list):
        raise ValueError("grid_energy_rates_json must be a JSON list")
    for index, rate in enumerate(rates):
        if not isinstance(rate, dict):
            raise ValueError(f"grid_energy_rates_json[{index}] must be an object")
    return rates


def grid_rate_options_for(dt: datetime, tz: ZoneInfo, options: dict) -> dict:
    local = dt.astimezone(tz)
    for rate in grid_energy_rates(options):
        months = rate.get("months", [])
        if not months or local.month in [int(month) for month in months]:
            return {**options, **rate}
    return options


def grid_energy_ledd(dt: datetime, tz: ZoneInfo, options: dict) -> float:
    local = dt.astimezone(tz)
    rate_options = grid_rate_options_for(dt, tz, options)
    is_weekday_day = local.weekday() < 5 and 6 <= local.hour < 22 and not is_norwegian_public_holiday(local.date())
    if is_weekday_day:
        return float(rate_options["grid_day_nok_per_kwh"])
    return float(rate_options["grid_night_weekend_nok_per_kwh"])


def has_custom_capacity_model(options: dict) -> bool:
    value = options.get("capacity_model_json")
    if isinstance(value, str):
        value = value.strip()
    return value not in (None, "", "{}", "[]")


def tier_label(from_kw: float, to_kw: float | None) -> str:
    if to_kw is None:
        return f"over {from_kw:g} kW"
    return f"{from_kw:g}-{to_kw:g} kW"


def normalize_capacity_tier(tier, index: int) -> dict:
    if isinstance(tier, dict):
        from_kw = float(tier.get("from_kw", tier.get("from", 0)))
        to_value = tier.get("to_kw", tier.get("to"))
        to_kw = None if to_value is None else float(to_value)
        amount = float(tier.get("monthly_nok", tier.get("amount", 0)))
        label = str(tier.get("label") or tier_label(from_kw, to_kw))
    elif isinstance(tier, (list, tuple)) and len(tier) >= 3:
        from_kw = float(tier[0])
        to_kw = None if tier[1] is None else float(tier[1])
        amount = float(tier[2])
        label = tier_label(from_kw, to_kw)
    else:
        raise ValueError(f"capacity tier {index} must be an object or [from_kw, to_kw, monthly_nok]")
    if to_kw is not None and to_kw <= from_kw:
        raise ValueError(f"capacity tier {index} has to_kw <= from_kw")
    return {
        "label": label,
        "from_kw": from_kw,
        "to_kw": to_kw,
        "monthly_nok": amount,
    }


def normalize_capacity_model(model: dict) -> dict:
    if not isinstance(model, dict):
        raise ValueError("capacity_model_json must be a JSON object")
    model_type = str(model.get("type", "monthly_top_n_daily_peaks"))
    normalized = {**model, "type": model_type}

    if model_type in {"disabled", "fixed_monthly"}:
        normalized["monthly_nok"] = float(model.get("monthly_nok", model.get("amount", 0.0)))
        normalized["tiers"] = []
        normalized["peak_count"] = int(model.get("peak_count", 0))
        normalized["capacity_basis_month_offset"] = int(model.get("capacity_basis_month_offset", 0))
        return normalized

    if model_type not in {"monthly_top_n_daily_peaks", "monthly_max_hour"}:
        raise ValueError(
            "capacity model type must be one of: "
            "monthly_top_n_daily_peaks, monthly_max_hour, fixed_monthly, disabled"
        )

    tiers = [normalize_capacity_tier(tier, index) for index, tier in enumerate(model.get("tiers", []))]
    tiers.sort(key=lambda item: item["from_kw"])
    if not tiers:
        raise ValueError(f"capacity model {model_type} requires at least one tier")
    for previous, current in zip(tiers, tiers[1:]):
        if previous["to_kw"] is not None and current["from_kw"] < previous["to_kw"]:
            raise ValueError("capacity model tiers must not overlap")
    normalized["tiers"] = tiers
    normalized["peak_count"] = max(int(model.get("peak_count", 3 if model_type == "monthly_top_n_daily_peaks" else 1)), 1)
    normalized["capacity_basis_month_offset"] = int(model.get("capacity_basis_month_offset", 0))
    return normalized


def legacy_capacity_model(options: dict) -> dict:
    profile = options.get("grid_capacity_profile", "custom")
    if profile in BUILTIN_CAPACITY_MODELS:
        return deepcopy(BUILTIN_CAPACITY_MODELS[profile])
    if profile != "custom":
        raise ValueError(
            f"Unknown grid_capacity_profile '{profile}'. "
            f"Use one of: {', '.join(sorted(BUILTIN_CAPACITY_MODELS))}, custom"
        )

    custom_tiers = parse_json_option(options.get("grid_capacity_tiers_json", "[]"), [], "grid_capacity_tiers_json")
    if custom_tiers:
        return {
            "type": "monthly_top_n_daily_peaks",
            "peak_count": 3,
            "tiers": custom_tiers,
        }

    fixed_monthly = float(options.get("grid_capacity_monthly_nok", 0.0))
    if fixed_monthly:
        return {"type": "fixed_monthly", "monthly_nok": fixed_monthly}
    return {"type": "disabled", "monthly_nok": 0.0}


def build_capacity_model(options: dict) -> dict:
    if INTERNAL_CAPACITY_MODEL in options:
        return options[INTERNAL_CAPACITY_MODEL]
    if has_custom_capacity_model(options):
        raw_model = parse_json_option(options.get("capacity_model_json"), {}, "capacity_model_json")
    else:
        raw_model = legacy_capacity_model(options)
    model = normalize_capacity_model(raw_model)
    options[INTERNAL_CAPACITY_MODEL] = model
    return model


def select_capacity_tier(value_kw: float, model: dict) -> tuple[dict | None, dict | None]:
    tiers = model.get("tiers", [])
    current = None
    next_tier = None
    for tier in tiers:
        lower = float(tier["from_kw"])
        upper = tier["to_kw"]
        if value_kw >= lower and (upper is None or value_kw < float(upper)):
            current = tier
            continue
        if value_kw < lower and next_tier is None:
            next_tier = tier
    if current is None and tiers:
        current = tiers[-1]
    if current:
        for tier in tiers:
            if tier["from_kw"] > current["from_kw"]:
                next_tier = tier
                break
    return current, next_tier


def warning_level(margin_kw: float | None, model: dict) -> str:
    if margin_kw is None:
        return "at_highest_tier"
    margin = float(model.get("warning_margin_kw", model.get("capacity_warning_margin_kw", 0.5)))
    if margin_kw <= 0:
        return "over_next_tier"
    if margin_kw <= margin:
        return "near_next_tier"
    return "ok"


def capacity_result_for_model(model: dict, day_peaks: dict, hourly_peaks: list[dict], options: dict) -> dict:
    model_type = model["type"]
    if model_type == "disabled":
        return {
            "capacity_model_type": "disabled",
            "capacity_metric_kw": 0.0,
            "capacity_peak_count": 0,
            "capacity_peak_days": [],
            "capacity_peak_timestamps": [],
            "capacity_peak_values_kw": [],
            "capacity_tier": "disabled",
            "capacity_current_tier": "disabled",
            "capacity_current_tier_min_kw": None,
            "capacity_current_tier_max_kw": None,
            "capacity_next_tier": "",
            "capacity_next_threshold_kw": None,
            "capacity_margin_to_next_kw": None,
            "capacity_over_tier_min_kw": 0.0,
            "capacity_cost": 0.0,
            "capacity_warning_level": "disabled",
        }
    if model_type == "fixed_monthly":
        amount = float(model.get("monthly_nok", 0.0))
        return {
            "capacity_model_type": "fixed_monthly",
            "capacity_metric_kw": 0.0,
            "capacity_peak_count": 0,
            "capacity_peak_days": [],
            "capacity_peak_timestamps": [],
            "capacity_peak_values_kw": [],
            "capacity_tier": "fixed",
            "capacity_current_tier": "fixed",
            "capacity_current_tier_min_kw": None,
            "capacity_current_tier_max_kw": None,
            "capacity_next_tier": "",
            "capacity_next_threshold_kw": None,
            "capacity_margin_to_next_kw": None,
            "capacity_over_tier_min_kw": 0.0,
            "capacity_cost": amount,
            "capacity_warning_level": "fixed",
        }

    peak_count = int(model.get("peak_count", 3))
    if model_type == "monthly_top_n_daily_peaks":
        peaks = sorted(day_peaks.values(), key=lambda item: item["kw"], reverse=True)[:peak_count]
        metric_kw = sum(item["kw"] for item in peaks) / len(peaks) if peaks else 0.0
    else:
        peaks = sorted(hourly_peaks, key=lambda item: item["kw"], reverse=True)[:1]
        metric_kw = peaks[0]["kw"] if peaks else 0.0

    current, next_tier = select_capacity_tier(metric_kw, model)
    current_min = current["from_kw"] if current else None
    current_max = current["to_kw"] if current else None
    next_threshold = next_tier["from_kw"] if next_tier else None
    margin = max(float(next_threshold) - metric_kw, 0.0) if next_threshold is not None else None
    over_min = max(metric_kw - float(current_min), 0.0) if current_min is not None else 0.0
    return {
        "capacity_model_type": model_type,
        "capacity_metric_kw": metric_kw,
        "capacity_peak_count": peak_count,
        "capacity_peak_days": [item["date"] for item in peaks],
        "capacity_peak_timestamps": [item.get("timestamp", item["date"]) for item in peaks],
        "capacity_peak_values_kw": [round(float(item["kw"]), 3) for item in peaks],
        "capacity_tier": current["label"] if current else "unknown",
        "capacity_current_tier": current["label"] if current else "unknown",
        "capacity_current_tier_min_kw": current_min,
        "capacity_current_tier_max_kw": current_max,
        "capacity_next_tier": next_tier["label"] if next_tier else "",
        "capacity_next_threshold_kw": next_threshold,
        "capacity_margin_to_next_kw": margin,
        "capacity_over_tier_min_kw": over_min,
        "capacity_cost": float(current["monthly_nok"]) if current else 0.0,
        "capacity_warning_level": warning_level(margin, {**options, **model}),
    }


def merge_capacity_results(results: list[dict], prorated_cost: float) -> dict:
    if not results:
        return capacity_result_for_model({"type": "disabled"}, {}, [], {})
    unique = lambda key: [str(item[key]) for item in results if item.get(key) not in (None, "")]
    margins = [item["capacity_margin_to_next_kw"] for item in results if item.get("capacity_margin_to_next_kw") is not None]
    next_candidates = [item for item in results if item.get("capacity_margin_to_next_kw") is not None]
    next_item = min(next_candidates, key=lambda item: item["capacity_margin_to_next_kw"]) if next_candidates else {}
    metric = max(float(item.get("capacity_metric_kw", 0.0)) for item in results)
    return {
        "capacity_model_type": " / ".join(dict.fromkeys(unique("capacity_model_type"))),
        "capacity_metric_kw": metric,
        "capacity_peak_count": max(int(item.get("capacity_peak_count", 0)) for item in results),
        "capacity_peak_days": results[0].get("capacity_peak_days", []),
        "capacity_peak_timestamps": results[0].get("capacity_peak_timestamps", []),
        "capacity_peak_values_kw": results[0].get("capacity_peak_values_kw", []),
        "capacity_tier": " / ".join(dict.fromkeys(unique("capacity_tier"))) or "unknown",
        "capacity_current_tier": " / ".join(dict.fromkeys(unique("capacity_current_tier"))) or "unknown",
        "capacity_current_tier_min_kw": min(
            (item["capacity_current_tier_min_kw"] for item in results if item.get("capacity_current_tier_min_kw") is not None),
            default=None,
        ),
        "capacity_current_tier_max_kw": max(
            (item["capacity_current_tier_max_kw"] for item in results if item.get("capacity_current_tier_max_kw") is not None),
            default=None,
        ),
        "capacity_next_tier": next_item.get("capacity_next_tier", ""),
        "capacity_next_threshold_kw": next_item.get("capacity_next_threshold_kw"),
        "capacity_margin_to_next_kw": min(margins) if margins else None,
        "capacity_over_tier_min_kw": max(float(item.get("capacity_over_tier_min_kw", 0.0)) for item in results),
        "capacity_cost": prorated_cost,
        "capacity_basis_month": " / ".join(dict.fromkeys(unique("capacity_basis_month"))),
        "capacity_basis_month_offset": results[0].get("capacity_basis_month_offset", 0),
        "capacity_basis_incomplete": any(bool(item.get("capacity_basis_incomplete", False)) for item in results),
        "capacity_warning_level": (
            "near_next_tier"
            if any(item.get("capacity_warning_level") == "near_next_tier" for item in results)
            else results[0].get("capacity_warning_level", "ok")
        ),
    }


def tariff_at(dt: datetime, options: dict) -> tuple[dict, str]:
    for period in options.get(INTERNAL_TARIFF_PERIODS, []):
        valid_from = period["valid_from"]
        valid_to = period["valid_to"]
        if valid_from and dt < valid_from:
            continue
        if valid_to and dt >= valid_to:
            continue
        return period["options"], period["name"]
    return options, str(options.get("profile", "custom"))


def tariff_slices_for_range(start: datetime, end: datetime, options: dict) -> list[tuple[dict, str, float]]:
    periods = options.get(INTERNAL_TARIFF_PERIODS, [])
    if not periods:
        return [(options, str(options.get("profile", "custom")), (end - start).total_seconds())]

    slices = []
    cursor = start
    for period in periods:
        period_start = period["valid_from"] or start
        period_end = period["valid_to"] or end
        overlap_start = max(start, period_start)
        overlap_end = min(end, period_end)
        if overlap_start < overlap_end:
            if cursor < overlap_start:
                slices.append((options, str(options.get("profile", "custom")), (overlap_start - cursor).total_seconds()))
            slices.append((period["options"], period["name"], (overlap_end - overlap_start).total_seconds()))
            cursor = max(cursor, overlap_end)
    if cursor < end:
        slices.append((options, str(options.get("profile", "custom")), (end - cursor).total_seconds()))
    return slices


def quota_limit_for_month(month_start: datetime, month_end: datetime, options: dict) -> float:
    limits = [
        float(tariff["norgespris_limit_kwh"])
        for tariff, _, _ in tariff_slices_for_range(month_start, month_end, options)
        if bool(tariff.get("norgespris_enabled", True))
    ]
    if not limits:
        return 0.0
    return max(limits)


def build_spot_rows(rows: list[dict], options: dict) -> list[tuple[int, float]]:
    multiplier = float(options.get("spot_price_multiplier_to_nok_per_kwh", 0.01))
    spot = []
    for row in rows:
        state = row.get("state")
        if state is None:
            continue
        spot.append((int(row["start"]), float(state) * multiplier))
    return sorted(spot)


def build_stats(energy_rows: list[dict], spot_rows: list[dict], options: dict) -> tuple[list[dict], dict]:
    tz = ZoneInfo(options["timezone"])
    sorted_spot = build_spot_rows(spot_rows, options)
    clean_rows = []
    daily_peak_by_month = defaultdict(dict)
    hourly_peaks_by_month = defaultdict(list)

    for row in sorted(energy_rows, key=lambda item: item["start"]):
        change = row.get("change")
        if change is None:
            continue
        kwh = max(float(change), 0.0)
        start = datetime.fromtimestamp(row["start"] / 1000, tz=tz)
        key = month_key(start, tz)
        clean_rows.append((int(row["start"]), start, kwh))
        hourly_peaks_by_month[key].append({"date": start.isoformat(), "timestamp": start.isoformat(), "kw": kwh})
        date_key = start.date().isoformat()
        if kwh >= daily_peak_by_month[key].get(date_key, {"kw": -1.0})["kw"]:
            daily_peak_by_month[key][date_key] = {
                "date": date_key,
                "timestamp": start.isoformat(),
                "kw": kwh,
            }

    monthly_fixed = {}
    for key, day_peaks in daily_peak_by_month.items():
        month_start, month_end = month_bounds(key, tz)
        month_seconds = (month_end - month_start).total_seconds()
        capacity_cost = 0.0
        provider_fixed = 0.0
        capacity_results = []
        tariff_names = []
        for tariff, tariff_name, seconds in tariff_slices_for_range(month_start, month_end, options):
            fraction = seconds / month_seconds if month_seconds else 0.0
            model = build_capacity_model(tariff)
            basis_offset = int(model.get("capacity_basis_month_offset", 0))
            basis_key = shift_month_key(key, basis_offset, tz)
            basis_day_peaks = daily_peak_by_month.get(basis_key, {})
            basis_hourly_peaks = hourly_peaks_by_month.get(basis_key, [])
            capacity = capacity_result_for_model(model, basis_day_peaks, basis_hourly_peaks, tariff)
            capacity["capacity_basis_month"] = basis_key
            capacity["capacity_basis_month_offset"] = basis_offset
            capacity["capacity_basis_incomplete"] = basis_offset != 0 and not (basis_day_peaks or basis_hourly_peaks)
            capacity_cost += capacity["capacity_cost"] * fraction
            provider_fixed += float(tariff["provider_monthly_nok"]) * fraction
            capacity_results.append(capacity)
            if tariff_name not in tariff_names:
                tariff_names.append(tariff_name)
        capacity_summary = merge_capacity_results(capacity_results, capacity_cost)
        monthly_fixed[key] = {
            **capacity_summary,
            "top_three_avg_kw": capacity_summary["capacity_metric_kw"],
            "provider_fixed": provider_fixed,
            "fixed_total": capacity_cost + provider_fixed,
            "quota_limit": quota_limit_for_month(month_start, month_end, options),
            "tariff_periods": ", ".join(tariff_names),
        }

    quota_left = {}
    fixed_added = set()
    cumulative = 0.0
    stats = []
    spot_index = 0
    last_spot_price = sorted_spot[0][1] if sorted_spot else float(options["norgespris_nok_per_kwh"])
    months = defaultdict(empty_cost_summary)
    weeks = defaultdict(empty_cost_summary)
    days = defaultdict(empty_cost_summary)

    for start_ms, start, kwh in clean_rows:
        while spot_index < len(sorted_spot) and sorted_spot[spot_index][0] <= start_ms:
            last_spot_price = sorted_spot[spot_index][1]
            spot_index += 1

        key = month_key(start, tz)
        tariff, _ = tariff_at(start, options)
        if key not in fixed_added:
            fixed = monthly_fixed[key]["fixed_total"]
            cumulative += fixed
            months[key]["fixed"] += fixed
            fixed_added.add(key)

        if key not in quota_left:
            quota_left[key] = float(monthly_fixed[key]["quota_limit"])

        if bool(tariff.get("norgespris_enabled", True)) and quota_left[key] > 0:
            quota_kwh = min(kwh, quota_left[key])
            spot_kwh = kwh - quota_kwh
            quota_left[key] -= quota_kwh
        else:
            quota_kwh = 0.0
            spot_kwh = kwh

        norgespris = float(tariff["norgespris_nok_per_kwh"])
        markup = float(tariff["provider_markup_nok_per_kwh"])
        power_cost = quota_kwh * norgespris + spot_kwh * last_spot_price
        markup_cost = kwh * markup
        grid_cost = kwh * grid_energy_ledd(start, tz, tariff)
        cost = power_cost + markup_cost + grid_cost
        cumulative += cost

        add_variable_cost(
            months[key],
            kwh,
            quota_kwh,
            spot_kwh,
            power_cost,
            markup_cost,
            grid_cost,
        )
        add_variable_cost(
            weeks[week_key(start, tz)],
            kwh,
            quota_kwh,
            spot_kwh,
            power_cost,
            markup_cost,
            grid_cost,
        )
        add_variable_cost(
            days[day_key(start, tz)],
            kwh,
            quota_kwh,
            spot_kwh,
            power_cost,
            markup_cost,
            grid_cost,
        )

        stats.append(
            {
                "start": start.isoformat(),
                "state": round(cumulative, 6),
                "sum": round(cumulative, 6),
            }
        )

    for key, fixed in monthly_fixed.items():
        months[key].update(fixed)
        months[key]["total"] += months[key]["fixed"]
        quota_limit = float(fixed["quota_limit"])
        months[key]["quota_left"] = max(quota_limit - months[key]["quota_kwh"], 0.0)
        months[key]["above_quota"] = months[key]["spot_kwh"] if quota_limit > 0 else 0.0

    return stats, {
        "days": dict(sorted(days.items())),
        "weeks": dict(sorted(weeks.items())),
        "months": dict(sorted(months.items())),
    }


def rounded(value: float, digits: int = 0) -> float:
    return round(float(value), digits)


def rounded_or_none(value, digits: int = 2) -> float | None:
    if value is None:
        return None
    return rounded(value, digits)


def monthly_cost_attributes(options: dict, summary: dict, now: datetime) -> dict:
    tz = ZoneInfo(options["timezone"])
    current_day = summary["days"].get(day_key(now, tz), empty_cost_summary())
    current_week = summary["weeks"].get(week_key(now, tz), empty_cost_summary())
    current_month = summary["months"].get(month_key(now, tz), empty_cost_summary())
    quota_limit = float(current_month.get("quota_limit", options["norgespris_limit_kwh"]))
    return {
        "friendly_name": "Power cost this month",
        "unit_of_measurement": "NOK",
        "device_class": "monetary",
        "icon": "mdi:cash",
        "last_calculated": now.isoformat(),
        "today_cost": rounded(current_day["total"], 0),
        "today_kwh": rounded(current_day["kwh"], 1),
        "week_cost": rounded(current_week["total"], 0),
        "week_kwh": rounded(current_week["kwh"], 1),
        "month_cost": rounded(current_month["total"], 0),
        "month_kwh": rounded(current_month["kwh"], 1),
        "month_variable_cost": rounded(current_month["variable_total"], 0),
        "month_fixed_cost": rounded(current_month["fixed"], 0),
        "month_power_cost": rounded(current_month["power_cost"], 0),
        "month_grid_energy_cost": rounded(current_month["grid_energy"], 0),
        "month_provider_markup_cost": rounded(current_month["provider_markup"], 0),
        "month_capacity_cost": rounded(current_month.get("capacity_cost", 0.0), 0),
        "month_provider_fixed_cost": rounded(current_month.get("provider_fixed", 0.0), 0),
        "norgespris_limit_kwh": rounded(quota_limit, 0),
        "norgespris_used_kwh": rounded(current_month["quota_kwh"], 1),
        "quota_left_kwh": rounded(max(quota_limit - current_month["kwh"], 0.0), 1),
        "above_quota_kwh": rounded(max(current_month["kwh"] - quota_limit, 0.0), 1),
        "spot_kwh": rounded(current_month["spot_kwh"], 1),
        "capacity_tier": current_month.get("capacity_tier", "unknown"),
        "top_three_avg_kw": rounded(current_month.get("top_three_avg_kw", 0.0), 2),
        "capacity_model_type": current_month.get("capacity_model_type", ""),
        "capacity_current_tier": current_month.get("capacity_current_tier", current_month.get("capacity_tier", "unknown")),
        "capacity_current_tier_min_kw": rounded_or_none(current_month.get("capacity_current_tier_min_kw"), 2),
        "capacity_current_tier_max_kw": rounded_or_none(current_month.get("capacity_current_tier_max_kw"), 2),
        "capacity_next_tier": current_month.get("capacity_next_tier", ""),
        "capacity_next_threshold_kw": rounded_or_none(current_month.get("capacity_next_threshold_kw"), 2),
        "capacity_margin_to_next_kw": rounded_or_none(current_month.get("capacity_margin_to_next_kw"), 2),
        "capacity_over_tier_min_kw": rounded_or_none(current_month.get("capacity_over_tier_min_kw"), 2),
        "capacity_metric_kw": rounded(current_month.get("capacity_metric_kw", 0.0), 2),
        "capacity_monthly_cost": rounded(current_month.get("capacity_cost", 0.0), 0),
        "capacity_peak_count": int(current_month.get("capacity_peak_count", 0)),
        "capacity_peak_days": current_month.get("capacity_peak_days", []),
        "capacity_peak_timestamps": current_month.get("capacity_peak_timestamps", []),
        "capacity_peak_values_kw": current_month.get("capacity_peak_values_kw", []),
        "capacity_basis_month": current_month.get("capacity_basis_month", month_key(now, tz)),
        "capacity_basis_month_offset": current_month.get("capacity_basis_month_offset", 0),
        "capacity_basis_incomplete": bool(current_month.get("capacity_basis_incomplete", False)),
        "capacity_warning_level": current_month.get("capacity_warning_level", ""),
        "tariff_periods": current_month.get("tariff_periods", ""),
    }


async def send_command(ws, msg_id: int, command: dict) -> dict:
    await ws.send(json.dumps({"id": msg_id, **command}))
    while True:
        message = json.loads(await ws.recv())
        if message.get("id") == msg_id:
            if not message.get("success"):
                raise RuntimeError(message)
            return message.get("result")


async def connect():
    token = os.environ["SUPERVISOR_TOKEN"]
    ws = await websockets.connect(CORE_WS_URL, open_timeout=10)
    greeting = json.loads(await ws.recv())
    if greeting.get("type") != "auth_required":
        raise RuntimeError(greeting)
    await ws.send(json.dumps({"type": "auth", "access_token": token}))
    auth = json.loads(await ws.recv())
    if auth.get("type") != "auth_ok":
        raise RuntimeError(auth)
    return ws


def set_core_state(entity_id: str, state: float, attributes: dict) -> None:
    payload = json.dumps({"state": round(state, 0), "attributes": attributes}).encode()
    req = request.Request(
        f"{CORE_API_URL}/states/{entity_id}",
        data=payload,
        headers={
            "Authorization": f"Bearer {os.environ['SUPERVISOR_TOKEN']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=10) as response:
        response.read()


async def import_costs(options: dict, replace: bool) -> None:
    energy_id = options["energy_entity"]
    spot_id = options["spot_entity"]
    cost_stat_id = options["cost_statistic_id"]
    cost_source = options["cost_source"]

    ws = await connect()
    try:
        energy = await send_command(
            ws,
            1,
            {
                "type": "recorder/statistics_during_period",
                "start_time": options["start_time"],
                "period": "hour",
                "statistic_ids": [energy_id],
                "types": ["sum", "change"],
            },
        )
        spot = await send_command(
            ws,
            2,
            {
                "type": "recorder/statistics_during_period",
                "start_time": options["start_time"],
                "period": "hour",
                "statistic_ids": [spot_id],
                "types": ["state"],
            },
        )
        prefs = await send_command(ws, 3, {"type": "energy/get_prefs"})
        stats, summary = build_stats(energy.get(energy_id, []), spot.get(spot_id, []), options)

        if replace:
            log(f"Clearing existing statistic {cost_stat_id}")
            await send_command(
                ws,
                4,
                {
                    "type": "recorder/clear_statistics",
                    "statistic_ids": [cost_stat_id],
                },
            )

        await send_command(
            ws,
            5,
            {
                "type": "recorder/import_statistics",
                "metadata": {
                    "has_mean": False,
                    "mean_type": 0,
                    "has_sum": True,
                    "name": "Energy cost",
                    "source": cost_source,
                    "statistic_id": cost_stat_id,
                    "unit_class": None,
                    "unit_of_measurement": "NOK",
                },
                "stats": stats,
            },
        )

        if options.get("update_energy_dashboard", True):
            sources = prefs["energy_sources"]
            grid_index = next(
                (idx for idx, source in enumerate(sources) if source.get("type") == "grid"),
                None,
            )
            if grid_index is None:
                raise RuntimeError("No grid source found in Energy dashboard preferences")
            sources[grid_index] = {
                **sources[grid_index],
                "stat_energy_from": energy_id,
                "stat_cost": cost_stat_id,
                "entity_energy_price": None,
                "number_energy_price": None,
            }
            await send_command(
                ws,
                6,
                {
                    "type": "energy/save_prefs",
                    "energy_sources": sources,
                    "device_consumption": prefs.get("device_consumption", []),
                    "device_consumption_water": prefs.get("device_consumption_water", []),
                },
            )

        monthly_cost_entity = str(options.get("monthly_cost_entity", "")).strip()
        if monthly_cost_entity:
            tz = ZoneInfo(options["timezone"])
            now = datetime.now(tz)
            current_key = month_key(now, tz)
            current_month = summary["months"].get(current_key)
            if current_month:
                current_month_cost = round(float(current_month["total"]), 0)
                if monthly_cost_entity.startswith("input_number."):
                    await send_command(
                        ws,
                        7,
                        {
                            "type": "call_service",
                            "domain": "input_number",
                            "service": "set_value",
                            "target": {"entity_id": monthly_cost_entity},
                            "service_data": {"value": current_month_cost},
                        },
                    )
                else:
                    await asyncio.to_thread(
                        set_core_state,
                        monthly_cost_entity,
                        current_month_cost,
                        monthly_cost_attributes(options, summary, now),
                    )
                log(f"Updated {monthly_cost_entity} to {current_month['total']:.0f} NOK")

    finally:
        await ws.close()

    REPORT_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    log(f"Imported {len(stats)} hourly rows into {cost_stat_id}")
    for key, month in summary["months"].items():
        log(
            f"{key}: {month['kwh']:.1f} kWh, over quota {month['above_quota']:.1f}, "
            f"capacity {month['capacity_tier']} {month['capacity_cost']:.0f} NOK, "
            f"total {month['total']:.2f} NOK"
        )


def seconds_until_daily_run(options: dict, now: datetime) -> float:
    hour, minute = [int(part) for part in options["daily_rebuild_time"].split(":", 1)]
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def next_daily_run(options: dict, now: datetime) -> datetime:
    hour, minute = [int(part) for part in options["daily_rebuild_time"].split(":", 1)]
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


async def scheduler() -> None:
    options = load_options()
    tz = ZoneInfo(options["timezone"])
    interval = max(int(options["update_interval_minutes"]), 15) * 60

    if options.get("replace_on_start", False):
        await import_costs(options, replace=True)
    else:
        await import_costs(options, replace=False)

    next_update = datetime.now(tz) + timedelta(seconds=interval)
    next_rebuild = next_daily_run(options, datetime.now(tz))
    while True:
        now = datetime.now(tz)
        sleep_for = min((next_update - now).total_seconds(), (next_rebuild - now).total_seconds())
        await asyncio.sleep(max(sleep_for, 1))
        now = datetime.now(tz)
        try:
            if now >= next_rebuild:
                await import_costs(options, replace=True)
                next_rebuild = next_daily_run(options, datetime.now(tz))
                next_update = datetime.now(tz) + timedelta(seconds=interval)
            elif now >= next_update:
                await import_costs(options, replace=False)
                next_update = datetime.now(tz) + timedelta(seconds=interval)
        except Exception as err:
            log(f"Import failed: {err}")


if __name__ == "__main__":
    try:
        asyncio.run(scheduler())
    except KeyboardInterrupt:
        log("Stopped")
