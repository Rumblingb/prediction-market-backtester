from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import cast

import polars as pl

from pm_bt.cli import run_cli
from pm_bt.common.utils import parse_ts_utc
from pm_bt.data import load_trades
from pm_bt.reporting import validate_run_directory


def _pick_top_market(
    *,
    venue: str,
    data_root: Path,
    start_ts: str | None,
    end_ts: str | None,
) -> str:
    ranks = (
        load_trades(
            venue,
            data_root=data_root,
            start_ts=parse_ts_utc(start_ts) if start_ts else None,
            end_ts=parse_ts_utc(end_ts) if end_ts else None,
        )
        .group_by("market_id")
        .agg(
            pl.col("size").sum().alias("volume_total"),
            pl.len().alias("trade_count"),
        )
        .sort(["volume_total", "trade_count"], descending=[True, True])
        .head(1)
        .collect()
    )
    if ranks.is_empty():
        raise ValueError(f"No trade data available for venue={venue}")
    return cast(str, ranks["market_id"][0])


def _resolve_new_run_dir(output_root: Path, existing: set[Path]) -> Path:
    current = {path for path in output_root.iterdir() if path.is_dir()}
    new_dirs = sorted(current - existing)
    if new_dirs:
        return new_dirs[-1]
    if not current:
        raise FileNotFoundError(f"No run directory found under {output_root}")
    return sorted(current)[-1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Profile a real CLI backtest and validate artifacts"
    )
    _ = parser.add_argument("--venue", default="kalshi", choices=["kalshi", "polymarket"])
    _ = parser.add_argument("--market", default=None)
    _ = parser.add_argument("--strategy", default="momentum")
    _ = parser.add_argument("--config", default="configs/momentum/default.yaml")
    _ = parser.add_argument("--data-root", default="data")
    _ = parser.add_argument("--output-root", default="output/profiling")
    _ = parser.add_argument("--start-ts", default=None)
    _ = parser.add_argument("--end-ts", default=None)
    _ = parser.add_argument("--bar-timeframe", default="5m")
    _ = parser.add_argument("--name", default="profile")
    _ = parser.add_argument("--report-path", default=None)
    args = parser.parse_args()

    venue = cast(str, args.venue)
    market_arg = cast(str | None, args.market)
    strategy = cast(str, args.strategy)
    config_path = cast(str, args.config)
    data_root = Path(cast(str, args.data_root))
    output_root = Path(cast(str, args.output_root))
    start_ts = cast(str | None, args.start_ts)
    end_ts = cast(str | None, args.end_ts)
    bar_timeframe = cast(str, args.bar_timeframe)
    name = cast(str, args.name)
    report_path_arg = cast(str | None, args.report_path)

    output_root.mkdir(parents=True, exist_ok=True)

    market = market_arg or _pick_top_market(
        venue=venue,
        data_root=data_root,
        start_ts=start_ts,
        end_ts=end_ts,
    )

    argv = [
        "backtest",
        "--venue",
        venue,
        "--market",
        market,
        "--strategy",
        strategy,
        "--config",
        config_path,
        "--data-root",
        str(data_root),
        "--output-root",
        str(output_root),
        "--bar-timeframe",
        bar_timeframe,
        "--name",
        name,
    ]
    if start_ts:
        argv.extend(["--start-ts", start_ts])
    if end_ts:
        argv.extend(["--end-ts", end_ts])

    existing_dirs = {path for path in output_root.iterdir() if path.is_dir()}
    t0 = perf_counter()
    exit_code = run_cli(argv)
    wall_time_s = perf_counter() - t0
    if exit_code != 0:
        return exit_code

    run_dir = _resolve_new_run_dir(output_root, existing_dirs)
    summary = validate_run_directory(run_dir)

    results_payload = cast(
        dict[str, object],
        json.loads((run_dir / "results.json").read_text(encoding="utf-8")),
    )
    report_payload = {
        "command": ["pm-bt", *argv],
        "market_id": market,
        "venue": venue,
        "wall_time_s": wall_time_s,
        "run_summary": summary.as_dict(),
        "timings": cast(dict[str, object], results_payload["timings"]),
        "trading_metrics": cast(dict[str, object], results_payload["trading_metrics"]),
        "forecasting_metrics": cast(dict[str, object], results_payload["forecasting_metrics"]),
    }

    report_path = Path(report_path_arg) if report_path_arg else run_dir / "profile_summary.json"
    _ = report_path.write_text(
        json.dumps(report_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report_payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
