# Performance Baseline

## Purpose

This document records a simple, reproducible CLI profiling baseline for a real local backtest run.
It is not a claim about every market or every machine. It is a concrete sample used to track
regressions.

## Reproduce

From the repository root:

```bash
make profile-sample
```

Equivalent direct command:

```bash
uv run python scripts/profile_backtest.py \
  --venue kalshi \
  --strategy momentum \
  --config configs/momentum/default.yaml \
  --data-root data \
  --output-root output/profiling \
  --bar-timeframe 5m
```

The script:

- runs a real `pm-bt backtest` code path
- auto-selects the top-volume market for the chosen venue when `--market` is omitted
- validates result coherence against `results.json`, `equity.csv`, and `trades.csv`
- writes `profile_summary.json` into the generated run directory

## Sample Baseline

Sample captured on **2026-03-07** from a local developer machine with the bundled local dataset.

- Venue: `kalshi`
- Strategy: `momentum`
- Config: `configs/momentum/default.yaml`
- Timeframe: `5m`
- Selected market: `PRES-2024-KH`
- Run directory: `/tmp/pm-bt-profile/20260307_100156_b9bcfc5`

Observed metrics from `profile_summary.json`:

- CLI wall-clock time: `5.67s`
- Engine `load_s`: `2.70s`
- Engine `execution_s`: `0.11s`
- Reporting `reporting_s`: `2.56s`
- Engine `total_s`: `5.67s`
- Bars processed: `10,763`
- Fills: `1,174`
- Final equity: `9909.00`
- Total PnL: `-91.00`
- Max drawdown: `0.93%`

## Interpretation

- The main runtime cost in this sample is data loading plus report generation, not bar-by-bar
  execution.
- `timings.total_s` is now coherent with the full run pipeline and is close to the outer CLI
  wall-clock time reported by the profiling script.
- The profiling script also checks basic coherence invariants:
  - `total_pnl == final_equity - initial_cash`
  - `fills_count == len(trades.csv)`
  - `bars_processed == len(equity.csv)`
  - turnover, max drawdown, and exposure metrics match the generated CSV artifacts
