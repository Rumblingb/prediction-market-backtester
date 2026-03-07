# Engine Contracts

## Purpose

This note summarizes the typed contracts that define the engine surface in `pm_bt`.
It is intentionally short and mirrors the current implementation rather than a future design.

## Core Data Models

The canonical domain models live in `src/pm_bt/common/models.py`.

- `Market`: venue, market identifier, outcome identifier, question/category metadata, close time,
  resolution state, winning outcome, resolution timestamp, and market structure.
- `TradeTick`: timestamped trade with implied-probability price, size, side, venue, and optional
  trade identifier / paid fee.
- `Bar`: time-bucketed OHLCV row with `vwap` and `trade_count`.
- `OrderIntent`: strategy output for a bar, including timestamp, side, quantity, and optional
  limit/target metadata.
- `Fill`: execution result with fill price, fees, slippage cost, and latency.
- `BacktestConfig`: typed run configuration for venue/market selection, bar timeframe, execution
  assumptions, and output roots.
- `RunResult`: reproducible run payload containing config, dataset slice, git commit, timings,
  trading metrics, forecasting metrics, and artifact paths.

## Loader Output Contracts

Loaders normalize venue-specific schemas into canonical columns.

Markets:

- `market_id`
- `venue`
- `outcome_id`
- `question`
- `category`
- `close_ts`
- `resolved`
- `winning_outcome`
- `resolved_ts`
- `market_structure`

Trades:

- `ts`
- `market_id`
- `outcome_id`
- `venue`
- `price`
- `size`
- `side`
- `trade_id`
- `fee_paid`

## Strategy Interface

The strategy contract lives in `src/pm_bt/strategies/base.py`.

- Input: `on_bar(bar: Bar, features: Mapping[str, object])`
- Output: `list[OrderIntent]`
- Semantics:
  - `bar` is the validated bar for the current decision step
  - `features` contains same-row derived features such as returns, rolling moments, or momentum
  - strategies may be stateless or stateful
  - execution, PnL accounting, and risk enforcement stay engine-side

## Reporting Contract

Single-run reporting writes:

- `config.json`
- `results.json`
- `equity.csv`
- `trades.csv`
- `equity_curve.png`
- `drawdown.png`
- `returns_distribution.png`

Batch mode writes:

- `summary.csv`
- `data_quality.json`
- `checkpoint.json`

Scanner mode writes:

- `alerts.json`
- `alerts.csv`
- optional `alerts.html`
