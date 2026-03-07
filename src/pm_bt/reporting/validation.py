from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import polars as pl


def _compute_max_drawdown(equity: pl.Series) -> float:
    peak = 0.0
    max_drawdown = 0.0
    for raw_value in cast(list[float], equity.to_list()):
        value = float(raw_value)
        peak = max(peak, value)
        if peak <= 0.0:
            continue
        max_drawdown = max(max_drawdown, (peak - value) / peak)
    return max_drawdown


def _assert_close(name: str, actual: float, expected: float, *, tolerance: float) -> None:
    if not math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance):
        raise ValueError(f"{name} mismatch: actual={actual} expected={expected}")


@dataclass(slots=True)
class RunCoherenceSummary:
    run_dir: Path
    run_id: str
    fills_count: int
    bars_processed: int
    final_equity: float
    total_pnl: float
    total_return: float
    max_drawdown: float

    def as_dict(self) -> dict[str, object]:
        return {
            "run_dir": str(self.run_dir),
            "run_id": self.run_id,
            "fills_count": self.fills_count,
            "bars_processed": self.bars_processed,
            "final_equity": self.final_equity,
            "total_pnl": self.total_pnl,
            "total_return": self.total_return,
            "max_drawdown": self.max_drawdown,
        }


def validate_run_directory(
    run_dir: Path,
    *,
    tolerance: float = 1e-9,
) -> RunCoherenceSummary:
    results_path = run_dir / "results.json"
    if not results_path.exists():
        raise FileNotFoundError(f"Missing results.json in {run_dir}")

    payload = cast(dict[str, object], json.loads(results_path.read_text(encoding="utf-8")))
    config = cast(dict[str, object], payload["config"])
    artifacts = cast(dict[str, str], payload["artifacts"])
    trading_metrics = cast(dict[str, float], payload["trading_metrics"])
    forecasting_metrics = cast(dict[str, float], payload["forecasting_metrics"])
    timings = cast(dict[str, float], payload["timings"])

    for artifact_name, artifact_path in artifacts.items():
        if not Path(artifact_path).exists():
            raise FileNotFoundError(f"Artifact path missing for {artifact_name}: {artifact_path}")

    if cast(str, payload["run_id"]) not in Path(artifacts["results_json"]).parent.as_posix():
        # Batch mode may use a run directory name that differs from run_id, so only validate
        # the results.json path parent matches the supplied run_dir.
        pass

    if payload.get("git_commit") is not None:
        git_commit = cast(str, payload["git_commit"])
        run_id = cast(str, payload["run_id"])
        if not run_id.endswith(git_commit):
            raise ValueError(f"run_id {run_id} does not end with git_commit {git_commit}")

    equity_df = pl.read_csv(
        Path(artifacts["equity_csv"]),
        try_parse_dates=True,
    )
    trades_df = pl.read_csv(
        Path(artifacts["trades_csv"]),
        try_parse_dates=True,
    )

    initial_cash = float(cast(float, config["initial_cash"]))
    final_equity = (
        float(cast(float, equity_df["equity"][-1])) if equity_df.height else float(initial_cash)
    )
    final_realized = float(cast(float, equity_df["realized_pnl"][-1])) if equity_df.height else 0.0
    final_unrealized = (
        float(cast(float, equity_df["unrealized_pnl"][-1])) if equity_df.height else 0.0
    )
    max_cash_at_risk = (
        float(cast(float, equity_df["cash_at_risk_gross"].max())) if equity_df.height else 0.0
    )
    max_gross_notional = (
        float(cast(float, equity_df["gross_notional_exposure"].max())) if equity_df.height else 0.0
    )
    total_notional = float(cast(float, trades_df["notional"].sum())) if trades_df.height else 0.0
    computed_drawdown = _compute_max_drawdown(equity_df["equity"]) if equity_df.height else 0.0

    _assert_close(
        "total_pnl",
        float(trading_metrics["total_pnl"]),
        final_equity - initial_cash,
        tolerance=tolerance,
    )
    _assert_close(
        "total_return",
        float(trading_metrics["total_return"]),
        (final_equity / initial_cash) - 1.0,
        tolerance=tolerance,
    )
    _assert_close(
        "realized_pnl",
        float(trading_metrics["realized_pnl"]),
        final_realized,
        tolerance=tolerance,
    )
    _assert_close(
        "unrealized_pnl",
        float(trading_metrics["unrealized_pnl"]),
        final_unrealized,
        tolerance=tolerance,
    )
    _assert_close(
        "max_cash_at_risk_gross",
        float(trading_metrics["max_cash_at_risk_gross"]),
        max_cash_at_risk,
        tolerance=tolerance,
    )
    _assert_close(
        "max_gross_exposure",
        float(trading_metrics["max_gross_exposure"]),
        max_cash_at_risk,
        tolerance=tolerance,
    )
    _assert_close(
        "max_gross_notional_exposure",
        float(trading_metrics["max_gross_notional_exposure"]),
        max_gross_notional,
        tolerance=tolerance,
    )
    _assert_close(
        "turnover",
        float(trading_metrics["turnover"]),
        total_notional / initial_cash,
        tolerance=tolerance,
    )
    _assert_close(
        "max_drawdown",
        float(trading_metrics["max_drawdown"]),
        computed_drawdown,
        tolerance=tolerance,
    )
    _assert_close(
        "fills_count",
        float(trading_metrics["fills_count"]),
        float(trades_df.height),
        tolerance=tolerance,
    )
    _assert_close(
        "bars_processed",
        float(trading_metrics["bars_processed"]),
        float(equity_df.height),
        tolerance=tolerance,
    )

    if equity_df.height:
        if not equity_df["ts"].is_sorted():
            raise ValueError("equity timestamps are not sorted")
    if trades_df.height:
        min_price = float(cast(float, trades_df["price_fill"].min()))
        max_price = float(cast(float, trades_df["price_fill"].max()))
        if min_price < 0.0 or max_price > 1.0:
            raise ValueError("fill prices must remain within implied-probability bounds [0, 1]")

    if forecasting_metrics.get("n_trades", 0.0) > 0.0:
        for metric_name in ("brier_score", "log_loss", "ece"):
            metric_value = float(forecasting_metrics[metric_name])
            if metric_value < 0.0:
                raise ValueError(f"{metric_name} must be non-negative")

    for timing_name, timing_value in timings.items():
        if float(timing_value) < 0.0:
            raise ValueError(f"{timing_name} must be non-negative")

    total_timing = float(timings["total_s"])
    component_sum = (
        float(timings["load_s"])
        + float(timings["features_s"])
        + float(timings["execution_s"])
        + float(timings["reporting_s"])
    )
    if total_timing + tolerance < component_sum:
        raise ValueError(
            "total_s must be at least the sum of load/features/execution/reporting timings"
        )

    return RunCoherenceSummary(
        run_dir=run_dir,
        run_id=cast(str, payload["run_id"]),
        fills_count=trades_df.height,
        bars_processed=equity_df.height,
        final_equity=final_equity,
        total_pnl=float(trading_metrics["total_pnl"]),
        total_return=float(trading_metrics["total_return"]),
        max_drawdown=float(trading_metrics["max_drawdown"]),
    )
