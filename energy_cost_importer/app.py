import asyncio
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import websockets


OPTIONS_PATH = Path("/data/options.json")
REPORT_PATH = Path("/data/last_report.json")
CORE_WS_URL = "ws://supervisor/core/websocket"


PROFILE_DEFAULTS = {
    "hyttekraft_fagne_hytte": {
        "provider_markup_nok_per_kwh": 0.0225,
        "provider_monthly_nok": 19.0,
        "grid_day_nok_per_kwh": 0.4516,
        "grid_night_weekend_nok_per_kwh": 0.3516,
        "grid_capacity_profile": "fagne_2026",
        "norgespris_enabled": True,
    },
    "vibb_lnett_norgespris": {
        "provider_markup_nok_per_kwh": 0.0,
        "provider_monthly_nok": 49.0,
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
    "grid_day_nok_per_kwh": 0.0,
    "grid_night_weekend_nok_per_kwh": 0.0,
    "grid_capacity_profile": "custom",
    "grid_capacity_monthly_nok": 0.0,
    "grid_capacity_tiers_json": "[]",
}


CAPACITY_TIERS = {
    "fagne_2026": [
        (0, 5, 360.0),
        (5, 10, 460.0),
        (10, 15, 560.0),
        (15, 20, 660.0),
        (20, 25, 760.0),
        (25, 50, 2200.0),
        (50, 75, 3200.0),
        (75, 100, 4200.0),
        (100, None, 5200.0),
    ],
    "lnett_2026_private": [
        (0, 2, 150.0),
        (2, 5, 250.0),
        (5, 10, 400.0),
        (10, 15, 650.0),
        (15, 20, 900.0),
        (20, 25, 1150.0),
        (25, None, 1150.0),
    ],
}


def log(message: str) -> None:
    print(f"[energy-cost-importer] {message}", flush=True)


def load_options() -> dict:
    with OPTIONS_PATH.open() as handle:
        options = json.load(handle)
    profile = options.get("profile", "custom")
    profile_defaults = {}
    if profile != "custom":
        if profile not in PROFILE_DEFAULTS:
            raise ValueError(
                f"Unknown profile '{profile}'. Use one of: "
                f"{', '.join(sorted(PROFILE_DEFAULTS))}, custom"
            )
        profile_defaults = PROFILE_DEFAULTS[profile]
    options = {**BASE_TARIFF_DEFAULTS, **profile_defaults, **options}
    if options.get("grid_capacity_profile") not in CAPACITY_TIERS:
        if options.get("grid_capacity_profile") != "custom":
            raise ValueError(
                f"Unknown grid_capacity_profile '{options.get('grid_capacity_profile')}'. "
                f"Use one of: {', '.join(sorted(CAPACITY_TIERS))}"
            )
    validate_options(options)
    return options


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


def month_key(dt: datetime, tz: ZoneInfo) -> str:
    return dt.astimezone(tz).strftime("%Y-%m")


def grid_energy_ledd(dt: datetime, tz: ZoneInfo, options: dict) -> float:
    local = dt.astimezone(tz)
    is_weekday_day = local.weekday() < 5 and 6 <= local.hour < 22
    if is_weekday_day:
        return float(options["grid_day_nok_per_kwh"])
    return float(options["grid_night_weekend_nok_per_kwh"])


def capacity_tier(avg_kw: float, options: dict) -> tuple[str, float]:
    profile = options.get("grid_capacity_profile", "custom")
    if profile == "custom":
        custom_tiers = json.loads(options.get("grid_capacity_tiers_json", "[]") or "[]")
        for tier in custom_tiers:
            lower, upper, amount = tier
            lower = float(lower)
            amount = float(amount)
            if upper is None and avg_kw >= lower:
                return f"over {lower:g} kW", amount
            if upper is not None and lower <= avg_kw < float(upper):
                return f"{lower:g}-{float(upper):g} kW", amount
        return "custom", float(options.get("grid_capacity_monthly_nok", 0.0))
    tiers = CAPACITY_TIERS[profile]
    for lower, upper, amount in tiers:
        if upper is None and avg_kw >= lower:
            return f"over {lower} kW", amount
        if upper is not None and lower <= avg_kw < upper:
            return f"{lower}-{upper} kW", amount
    return "unknown", 0.0


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
    daily_max_by_month = defaultdict(lambda: defaultdict(float))

    for row in sorted(energy_rows, key=lambda item: item["start"]):
        change = row.get("change")
        if change is None:
            continue
        kwh = max(float(change), 0.0)
        start = datetime.fromtimestamp(row["start"] / 1000, tz=tz)
        clean_rows.append((int(row["start"]), start, kwh))
        daily_max_by_month[month_key(start, tz)][start.date()] = max(
            daily_max_by_month[month_key(start, tz)][start.date()],
            kwh,
        )

    monthly_fixed = {}
    for key, day_peaks in daily_max_by_month.items():
        top_three = sorted(day_peaks.values(), reverse=True)[:3]
        avg_kw = sum(top_three) / len(top_three) if top_three else 0.0
        tier_name, capacity_cost = capacity_tier(avg_kw, options)
        provider_fixed = float(options["provider_monthly_nok"])
        monthly_fixed[key] = {
            "top_three_avg_kw": avg_kw,
            "capacity_tier": tier_name,
            "capacity_cost": capacity_cost,
            "provider_fixed": provider_fixed,
            "fixed_total": capacity_cost + provider_fixed,
        }

    quota_limit = float(options["norgespris_limit_kwh"])
    norgespris = float(options["norgespris_nok_per_kwh"])
    markup = float(options["provider_markup_nok_per_kwh"])
    norgespris_enabled = bool(options.get("norgespris_enabled", True))
    quota_left = defaultdict(lambda: quota_limit)
    fixed_added = set()
    cumulative = 0.0
    stats = []
    spot_index = 0
    last_spot_price = sorted_spot[0][1] if sorted_spot else norgespris
    summary = defaultdict(
        lambda: {
            "kwh": 0.0,
            "quota_kwh": 0.0,
            "spot_kwh": 0.0,
            "power_cost": 0.0,
            "provider_markup": 0.0,
            "grid_energy": 0.0,
            "fixed": 0.0,
            "total": 0.0,
        }
    )

    for start_ms, start, kwh in clean_rows:
        while spot_index < len(sorted_spot) and sorted_spot[spot_index][0] <= start_ms:
            last_spot_price = sorted_spot[spot_index][1]
            spot_index += 1

        key = month_key(start, tz)
        if key not in fixed_added:
            fixed = monthly_fixed[key]["fixed_total"]
            cumulative += fixed
            summary[key]["fixed"] += fixed
            fixed_added.add(key)

        if norgespris_enabled:
            quota_kwh = min(kwh, quota_left[key])
            spot_kwh = kwh - quota_kwh
            quota_left[key] -= quota_kwh
        else:
            quota_kwh = 0.0
            spot_kwh = kwh

        power_cost = quota_kwh * norgespris + spot_kwh * last_spot_price
        markup_cost = kwh * markup
        grid_cost = kwh * grid_energy_ledd(start, tz, options)
        cost = power_cost + markup_cost + grid_cost
        cumulative += cost

        summary[key]["kwh"] += kwh
        summary[key]["quota_kwh"] += quota_kwh
        summary[key]["spot_kwh"] += spot_kwh
        summary[key]["power_cost"] += power_cost
        summary[key]["provider_markup"] += markup_cost
        summary[key]["grid_energy"] += grid_cost
        summary[key]["total"] += cost

        stats.append(
            {
                "start": start.isoformat(),
                "state": round(cumulative, 6),
                "sum": round(cumulative, 6),
            }
        )

    for key, fixed in monthly_fixed.items():
        summary[key].update(fixed)
        summary[key]["total"] += summary[key]["fixed"]
        summary[key]["quota_left"] = max(quota_limit - summary[key]["kwh"], 0.0)
        summary[key]["above_quota"] = max(summary[key]["kwh"] - quota_limit, 0.0)

    return stats, {"months": dict(sorted(summary.items()))}


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
            current_key = month_key(datetime.now(tz), tz)
            current_month = summary["months"].get(current_key)
            if current_month:
                await send_command(
                    ws,
                    7,
                    {
                        "type": "call_service",
                        "domain": "input_number",
                        "service": "set_value",
                        "target": {"entity_id": monthly_cost_entity},
                        "service_data": {"value": round(float(current_month["total"]), 0)},
                    },
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
