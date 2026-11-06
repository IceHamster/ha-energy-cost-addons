"""Regression cases based on the official tariff sources linked in DOCS.md.

Run from the repository root: python3 -m unittest discover -s tests -v
Only standard-library modules are needed; Home Assistant calls are mocked.
"""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from energy_cost_importer import app


TZ = ZoneInfo("Europe/Oslo")


def local(value):
    return datetime.fromisoformat(value).replace(tzinfo=TZ)


def row(value, kwh):
    return {"start": int(local(value).timestamp() * 1000), "change": kwh}


def full_month(key, kwh=6):
    start, end = app.month_bounds(key, TZ)
    return [
        {"start": timestamp, "change": kwh}
        for timestamp in range(int(start.timestamp() * 1000), int(end.timestamp() * 1000), 3_600_000)
    ]


def options(grid, start="2026-01-01T00:00:00+01:00", **overrides):
    raw = {
        "profile": "custom",
        "grid_tariff_profile": grid,
        "timezone": "Europe/Oslo",
        "start_time": start,
        "energy_entity": "sensor.energy",
        "spot_entity": "sensor.spot",
        "cost_statistic_id": "energy_cost_importer:total",
        "cost_source": "energy_cost_importer",
        "update_energy_dashboard": False,
        **overrides,
    }
    resolved = app.resolve_options(raw)
    app.validate_capacity_profile(resolved)
    resolved[app.INTERNAL_TARIFF_PERIODS] = app.build_tariff_periods(raw, resolved)
    return resolved


class GridTariffTests(unittest.TestCase):
    def test_current_published_energy_prices_and_time_boundaries(self):
        for grid, day, night in [
            ("fagne_2026_private", .4516, .3516),
            ("lnett_2026_private", .4216, .2716),
            ("elvia_2026_private", .4640, .3140),
            ("bkk_2026_private", .4613, .2329),
            ("eviny_bkk_2026_private", .4613, .2329),
        ]:
            cfg = options(grid)
            for instant, expected in [
                ("2026-11-06T05:00", night),
                ("2026-11-06T06:00", day),
                ("2026-11-06T21:00", day),
                ("2026-11-06T22:00", night),
                ("2026-11-07T12:00", night),
                ("2026-12-25T12:00", night),
            ]:
                with self.subTest(grid=grid, instant=instant):
                    self.assertEqual(app.grid_energy_ledd(local(instant), TZ, cfg), expected)

    def test_elvia_july_change_updates_both_energy_and_capacity(self):
        rows = [row(f"2026-{month:02}-{day:02}T12:00", 6) for month in [6, 7] for day in [1, 2, 3]]
        _, summary = app.build_stats(rows, [], options("elvia_2026_private"))
        june, july = (summary["months"][f"2026-{month}"] for month in ["06", "07"])
        self.assertEqual(june["capacity_cost"], 300)
        self.assertEqual(july["capacity_cost"], 420)
        self.assertAlmostEqual(june["grid_energy"], 18 * .364)
        self.assertAlmostEqual(july["grid_energy"], 18 * .464)
        self.assertAlmostEqual(june["total"], 300 + 18 * .364)
        self.assertAlmostEqual(july["total"], 420 + 18 * .464)

    def test_elvia_all_historical_capacity_steps(self):
        cfg = options("elvia_2026_private")
        for month, amounts in [
            (1, [125,190,300,410,520,630,1175,1720,2270,4570]),
            (7, [150,250,420,585,755,925,1760,2600,3440,6800]),
            (2, [125,190,300,410,520,630,1175,1720,2270,4570]),
        ]:
            # Reusing the options must not cache July's prices for January.
            model = app.build_capacity_model(cfg, month)
            for kw, amount in zip([1,3,6,12,17,22,30,60,80,110], amounts):
                with self.subTest(month=month, kw=kw):
                    self.assertEqual(app.select_capacity_tier(kw, model)[0]["monthly_nok"], amount)

    def test_elvia_energy_changes_at_july_boundary(self):
        cfg = options("elvia_2026_private")
        for instant, expected in [
            ("2026-06-30T21:00", .364),
            ("2026-06-30T22:00", .264),
            ("2026-07-01T00:00", .314),
            ("2026-07-01T06:00", .464),
            ("2026-04-06T12:00", .264),
        ]:
            self.assertEqual(app.grid_energy_ledd(local(instant), TZ, cfg), expected)

    def test_bkk_2025_all_price_periods_and_alias(self):
        for grid in ["bkk_2025_private", "eviny_bkk_2025_private"]:
            cfg = options(grid, start="2025-01-01T00:00:00+01:00")
            for instant, day, night in [
                ("2025-01-06", .5094, .3821),
                ("2025-03-03", .5094, .3821),
                ("2025-04-01", .5986, .4713),
                ("2025-08-04", .5986, .4713),
                ("2025-09-01", .5837, .4615),
                ("2025-10-01", .5287, .4065),
                ("2025-12-01", .5287, .4065),
            ]:
                with self.subTest(grid=grid, instant=instant):
                    self.assertEqual(app.grid_energy_ledd(local(instant+"T12:00"), TZ, cfg), day)
                    self.assertEqual(app.grid_energy_ledd(local(instant+"T23:00"), TZ, cfg), night)

    def test_bkk_capacity_uses_billed_month_prices_and_previous_month_peaks(self):
        for month, previous, amount in [(8,"2025-07",430), (9,"2025-08",415), (10,"2025-09",415)]:
            cfg = options("bkk_2025_private", start=f"2025-{month:02}-01T00:00:00+02:00")
            _, summary = app.build_stats(full_month(previous) + [row(f"2025-{month:02}-01T12:00", 1)], [], cfg)
            self.assertEqual(list(summary["months"]), [f"2025-{month:02}"])
            result = summary["months"][f"2025-{month:02}"]
            self.assertEqual(result["capacity_basis_month"], previous)
            self.assertEqual(result["capacity_cost"], amount)
            self.assertEqual(result["kwh"], 1)

    def test_previous_year_context_is_not_billed_or_counted_against_quota(self):
        cfg = options("bkk_2026_private", norgespris_enabled=True, norgespris_limit_kwh=1000, norgespris_nok_per_kwh=.5)
        stats, summary = app.build_stats(full_month("2025-12") + [row("2026-01-02T12:00", 1)], [], cfg)
        self.assertEqual(len(stats), 1)
        self.assertEqual(list(summary["months"]), ["2026-01"])
        result = summary["months"]["2026-01"]
        self.assertEqual(result["capacity_cost"], 415)
        self.assertEqual(result["quota_kwh"], 1)
        self.assertAlmostEqual(result["total"], 415 + .5 + .4613)

    def test_missing_or_partial_previous_month_refuses_inaccurate_costs(self):
        cfg = options("bkk_2026_private", start="2026-11-01T00:00:00+01:00")
        current = row("2026-11-02T12:00", 1)
        complete = full_month("2026-10")
        for history in [[], complete[:-1], [*complete[:-1], complete[0]], [{**item, "change": None} for item in complete]]:
            with self.subTest(rows=len(history)):
                with self.assertRaisesRegex(ValueError, "complete hourly consumption statistics for 2026-10"):
                    app.build_stats([*history, current], [], cfg)

    def test_previous_month_coverage_handles_both_dst_changes(self):
        for month, previous, hours in [("04","2026-03",743), ("11","2026-10",745)]:
            history = full_month(previous)
            self.assertEqual(len(history), hours)
            cfg = options("bkk_2026_private", start=f"2026-{month}-01T00:00:00")
            _, summary = app.build_stats(history + [row(f"2026-{month}-02T12:00", 1)], [], cfg)
            self.assertEqual(summary["months"][f"2026-{month}"]["capacity_cost"], 415)

    def test_zero_consumption_is_valid_previous_month_data(self):
        cfg = options("bkk_2026_private")
        _, summary = app.build_stats(full_month("2025-12", 0) + [row("2026-01-02T12:00",1)], [], cfg)
        self.assertEqual(summary["months"]["2026-01"]["capacity_cost"], 155)

    def test_capacity_history_start_includes_dated_periods_and_year_boundary(self):
        self.assertEqual(app.capacity_history_start(options("bkk_2026_private")), "2025-12-01T00:00:00+01:00")
        cfg = options("", tariff_periods_json=json.dumps([
            {"valid_from":"2026-01-01", "grid_tariff_profile":"bkk_2026_private"}
        ]))
        self.assertEqual(app.capacity_history_start(cfg), "2025-12-01T00:00:00+01:00")
        self.assertEqual(app.capacity_history_start(options("elvia_2026_private")), "2026-01-01T00:00:00+01:00")

    def test_capacity_peaks_must_be_from_distinct_days(self):
        rows = [row("2026-11-02T08:00",10),row("2026-11-02T09:00",9),row("2026-11-03T08:00",4),row("2026-11-04T08:00",4)]
        _, summary = app.build_stats(rows, [], options("elvia_2026_private"))
        self.assertEqual(summary["months"]["2026-11"]["capacity_metric_kw"], 6)

    def test_lnett_does_not_invent_prices_at_or_above_25_kw(self):
        model = app.build_capacity_model(options("lnett_2026_private"))
        self.assertEqual(app.select_capacity_tier(24.999, model)[0]["monthly_nok"], 1150)
        for kw in [25,30,100]:
            with self.assertRaisesRegex(ValueError, "outside the configured tariff tiers"):
                app.select_capacity_tier(kw, model)

    def test_verified_custom_capacity_can_cover_lnett_high_usage(self):
        cfg = options("lnett_2026_private", capacity_model_json=json.dumps({"type":"fixed_monthly", "monthly_nok":2000}))
        _, summary = app.build_stats([row("2026-11-02T12:00",30)], [], cfg)
        self.assertEqual(summary["months"]["2026-11"]["capacity_cost"], 2000)

    def test_manual_rates_and_capacity_override_historical_defaults(self):
        cfg = options("elvia_2026_private", grid_day_nok_per_kwh=.9,
                      capacity_model_json=json.dumps({"type":"fixed_monthly", "monthly_nok":123}),
                      tariff_periods_json=json.dumps([{"valid_from":"2026-01-01", "provider_monthly_nok":49}]))
        tariff, _ = app.tariff_at(local("2026-01-06T12:00"),cfg)
        self.assertEqual(app.grid_energy_ledd(local("2026-01-06T12:00"),TZ,tariff), .9)
        self.assertEqual(app.build_capacity_model(tariff,1)["monthly_nok"],123)
        self.assertEqual(app.build_capacity_model(tariff,7)["monthly_nok"],123)

    def test_user_seasonal_rates_remain_authoritative(self):
        cfg = options("elvia_2026_private", grid_day_nok_per_kwh=.9,
                      grid_energy_rates_json=json.dumps([{"months":[1],"grid_day_nok_per_kwh":.1}]))
        self.assertEqual(app.grid_energy_ledd(local("2026-01-06T12:00"),TZ,cfg), .1)

    def test_default_empty_options_preserve_builtin_seasonal_rates(self):
        cfg = options("elvia_2026_private", grid_energy_rates_json="[]")
        self.assertEqual(app.grid_energy_ledd(local("2026-01-06T12:00"),TZ,cfg), .364)

    def test_empty_grid_option_keeps_legacy_profile_identity(self):
        cfg = options("", profile="vibb_lnett_norgespris")
        self.assertEqual(cfg["grid_tariff_profile"], "lnett_2026_private")
        self.assertEqual(app.grid_energy_ledd(local("2026-11-06T12:00"),TZ,cfg), .4216)

    def test_dated_grid_switch_uses_each_profiles_history(self):
        cfg = options("elvia_2026_private", start="2025-10-01T00:00:00+02:00", tariff_periods_json=json.dumps([
            {"valid_from":"2025-10-01", "valid_to":"2026-01-01", "grid_tariff_profile":"bkk_2025_private"}
        ]))
        for instant, expected in [("2025-10-01T12:00",.5287), ("2026-01-06T12:00",.364)]:
            tariff, _ = app.tariff_at(local(instant),cfg)
            self.assertEqual(app.grid_energy_ledd(local(instant),TZ,tariff),expected)

    def test_year_presets_reject_unverified_years(self):
        for grid, year in [("elvia_2026_private",2025),("fagne_2026_private",2027),("bkk_2025_private",2026)]:
            cfg = options(grid,start=f"{year}-01-01T00:00:00")
            with self.assertRaisesRegex(ValueError,"verified only for"):
                app.build_stats([row(f"{year}-01-02T12:00",1)],[],cfg)

    def test_custom_prices_work_outside_builtin_years(self):
        cfg = options("custom",start="2027-01-01",grid_day_nok_per_kwh=.7,grid_capacity_monthly_nok=200)
        _, summary = app.build_stats([row("2027-01-04T12:00",1)],[],cfg)
        self.assertAlmostEqual(summary["months"]["2027-01"]["total"],200.7)

    def test_switching_to_custom_does_not_keep_builtin_monthly_changes(self):
        cfg = options("elvia_2026_private")
        tariff = app.build_period_options({"grid_tariff_profile":"custom"},cfg)
        self.assertEqual(app.grid_energy_ledd(local("2026-01-06T12:00"),TZ,tariff),.464)

    def test_bkk_billing_spans_a_dated_year_change(self):
        cfg = options("bkk_2026_private",start="2025-12-01",tariff_periods_json=json.dumps([
            {"valid_from":"2025-12-01", "valid_to":"2026-01-01", "grid_tariff_profile":"bkk_2025_private"}
        ]))
        _, summary = app.build_stats(full_month("2025-11") + full_month("2025-12") + [row("2026-01-02T12:00",1)],[],cfg)
        self.assertEqual(list(summary["months"]),["2025-12","2026-01"])
        self.assertEqual(summary["months"]["2025-12"]["capacity_cost"],415)
        self.assertEqual(summary["months"]["2026-01"]["capacity_cost"],415)

    def test_filtering_import_start_distinguishes_repeated_autumn_hour(self):
        cfg = options("custom",start="2026-10-25T02:00:00+01:00",grid_night_weekend_nok_per_kwh=1)
        # The two local 02:00 hours have different UTC timestamps.
        first = int(datetime.fromisoformat("2026-10-25T02:00:00+02:00").timestamp()*1000)
        second = int(datetime.fromisoformat("2026-10-25T02:00:00+01:00").timestamp()*1000)
        stats, summary = app.build_stats([{"start":first,"change":10},{"start":second,"change":1}],[],cfg)
        self.assertEqual(len(stats),1)
        self.assertEqual(summary["months"]["2026-10"]["total"],1)


class ImportTests(unittest.IsolatedAsyncioTestCase):
    async def run_import(self, history):
        cfg = options("bkk_2026_private",start="2026-11-01T00:00:00+01:00")
        ws = AsyncMock()
        commands = []

        async def send(_ws, _id, command):
            commands.append(command)
            if command.get("statistic_ids") == ["sensor.energy"]:
                return {"sensor.energy": history + [row("2026-11-02T12:00",1)]}
            return {}

        with tempfile.TemporaryDirectory() as temp:
            with patch.object(app,"connect",AsyncMock(return_value=ws)), \
                 patch.object(app,"send_command",side_effect=send), \
                 patch.object(app,"REPORT_PATH",Path(temp)/"report.json"), \
                 patch.object(app,"log"):
                try:
                    await app.import_costs(cfg,replace=True)
                finally:
                    self.commands = commands
                    ws.close.assert_awaited_once()

    async def test_import_fetches_context_but_publishes_only_requested_dates(self):
        await self.run_import(full_month("2026-10"))
        self.assertEqual(self.commands[0]["start_time"],"2026-10-01T00:00:00+02:00")
        self.assertEqual(self.commands[1]["start_time"],"2026-11-01T00:00:00+01:00")
        imported = next(command for command in self.commands if command["type"] == "recorder/import_statistics")
        self.assertEqual(len(imported["stats"]),1)
        self.assertAlmostEqual(imported["stats"][0]["sum"],415.4613)

    async def test_incomplete_basis_never_clears_or_imports_statistics(self):
        with self.assertRaisesRegex(ValueError,"complete hourly consumption statistics"):
            await self.run_import([])
        self.assertFalse(any(command["type"] in {"recorder/clear_statistics","recorder/import_statistics"} for command in self.commands))


if __name__ == "__main__":
    unittest.main()
