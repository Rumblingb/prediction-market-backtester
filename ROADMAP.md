# Build Plan — Prediction Market Backtester (MVP → Prod)

This document is a step-by-step execution plan for an AI to build a clean, production-grade project quickly.
Each phase has a checklist with acceptance criteria.

Goal: a quant-style backtesting engine for prediction markets (Polymarket + Kalshi) built on Parquet datasets, with realistic execution simulation (bid/ask, fees, slippage, latency) and reproducible results. UI can be added on top of the same engine for run orchestration and analysis, but core logic remains engine-side.

---

## 0A) Domain understanding gate (before implementation)

### Tasks
- Write and maintain a short domain note: `docs/prediction-markets-vs-tradfi.md`.
- Define project vocabulary so it is prediction-market-native (not copy-pasted from equities/FX).
- Explicitly document:
  - binary payoff and resolution flow (`0/1` settlement)
  - market-implied probability interpretation (and why it can deviate from true probabilities)
  - thin/event-driven liquidity and its impact on execution assumptions
  - market-structure assumptions by venue/era (for example CLOB-style vs AMM-style periods)
  - market-structure consistency checks (Yes/No complements, mutually exclusive outcomes)

### Checklist (acceptance)
- [x] The team can explain core differences vs traditional financial markets in 2–3 minutes.
- [x] Assumptions used by the simulator are documented and justified in domain terms.
- [x] `docs/prediction-markets-vs-tradfi.md` exists and is referenced by README.
- [x] Forecasting quality metrics are explicitly separated from trading performance metrics in docs and results.

---

## 0) Non-negotiables (apply in every phase)

### Principles
- Correctness > features.
- Reproducibility is mandatory (config + git commit hash stored with results).
- Performance by design (Parquet scans, lazy evaluation, avoid Python loops over ticks).
- Type hints everywhere (public functions, dataclasses/pydantic models).
- Tests for critical math (PnL, execution, fees, slippage).
- Domain correctness is mandatory (binary settlement, resolution, implied probability semantics).

### Definition of Done (global)
- `make test` passes
- `make lint` passes
- one end-to-end backtest run works from scratch using sample data
- results artifacts are generated in `output/runs/<run-id>/...`
- prediction-market-specific evaluation (Brier and/or log loss) is produced on resolved markets

---

## 1) Repo bootstrap (Day 0)

### Tasks
- Create repository: `prediction-market-backtester`
- Add basic structure and tooling:
  - Python 3.11+
  - `uv` (or Poetry) for dependency management
  - `ruff`, `basedpyright`, `pytest`
  - `pre-commit`
  - GitHub Actions workflow (lint + typecheck + tests)
  - data bootstrap/index commands:
    - `make setup` (download + extract dataset archive)
    - `make index` (non-interactive indexers orchestration)
- Create folder structure:

.
├── src/pm_bt/
│ ├── common/
│ │ ├── models.py
│ │ ├── types.py
│ │ └── utils.py
│ ├── data/
│ ├── features/
│ ├── execution/
│ ├── strategies/
│ ├── backtest/
│ ├── reporting/
│ ├── cli.py
│ └── __init__.py
├── tests/
├── configs/
├── output/
├── scripts/
│ ├── setup_data.sh
│ └── index_data.py
├── vendor/
│ └── prediction-market-analysis/
├── THIRD_PARTY_NOTICES.md
├── .env.example
├── README.md
├── SKILLS.md
└── pyproject.toml

### Checklist (acceptance)
- [x] `uv sync` (or `poetry install`) works on a clean machine
- [x] `ruff check .` passes
- [x] `basedpyright` passes (recommended mode to start, strictness can increase later)
- [x] `pytest` runs (even if empty)
- [x] `make setup` works with `DATA_URL` configured
- [x] `make index SOURCE=kalshi MODE=markets` runs from a clean machine
- [ ] GitHub Actions runs on PR/push and is green

---

## 2) Data contract + minimal dataset (Day 0–1)

### Tasks
- Define internal data contracts (typed models):
  - `src/pm_bt/common/models.py` for shared Pydantic models
  - `src/pm_bt/common/types.py` for type aliases (`MarketId`, `Timestamp`, etc.)
  - `src/pm_bt/common/utils.py` for generic helpers (small, pure, reusable)
  - Market metadata
  - Resolution fields (resolved flag, winning outcome, resolution timestamp if available)
  - Trade / tick
  - Bar (OHLCV)
  - Order + Fill
  - BacktestConfig
  - RunResult
- Create a **tiny deterministic fixture dataset** for tests:
  - `tests/fixtures/trades_small.csv` (or tiny Parquet)
  - A few trades across 2 markets and 2 outcomes
  - Known expected PnL under a simple strategy

### Checklist (acceptance)
- [x] `src/pm_bt/common/models.py` (or equivalent) exists with typed models
- [x] Fixture dataset is small (< 100 KB) and deterministic
- [x] At least 1 unit test validates parsing/typing of the fixture data
- [x] Fixture includes at least one resolved market for calibration tests

---

## 3) Parquet loaders (MVP foundation) (Day 1)

### Tasks
- Implement Parquet loaders using Polars LazyFrames (preferred) or DuckDB:
  - `load_markets(venue, filters...)`
  - `load_trades(venue, market_id, date_range...)`
- Ensure:
  - predicate pushdown works (filters applied before materialization)
  - incremental date-range reads are possible
  - memory usage is controlled (no reading “everything” unless explicitly requested)

### Checklist (acceptance)
- [x] Loader functions exist and are covered by tests using fixture data
- [x] Loaders support basic filtering: `venue`, `market_id`, `start_ts`, `end_ts`
- [x] Loading a single market is O(data for that market), not O(all data)

---

## 4) Bar builder + basic features (MVP) (Day 1–2)

### Tasks
- Implement bar generation from trades:
  - time-based bars (e.g., 1m, 5m, 1h)
  - fields: open/high/low/close, volume, vwap, trade_count
- Implement minimal indicators:
  - returns
  - rolling mean
  - rolling std / volatility proxy
  - momentum signal

### Checklist (acceptance)
- [x] `build_bars(trades, timeframe)` produces correct OHLCV on fixture dataset
- [x] Unit tests validate at least one bar computation (open/high/low/close + vwap)
- [x] Feature pipeline runs in vectorized form (Polars expressions), not Python loops

---

## 5) Execution simulator v1 (the critical differentiator) (Day 2)

### Tasks
Implement a realistic-but-simple execution model:

- Fill prices:
  - Buy fills at `ask = price + spread/2`
  - Sell fills at `bid = price - spread/2`
  - If order book is not available: estimate spread from recent trades or config default
- Fees:
  - configurable fee model (percent of notional; start simple)
- Slippage:
  - configurable slippage model:
    - `slippage_bps` per trade, OR
    - size-based: `slippage = k * (qty / recent_volume)`
- Latency:
  - apply decision lag of N seconds/bars (shift strategy signal)
- Risk constraints:
  - max position size per market/outcome
  - max gross exposure
  - optional: stop after max drawdown

### Checklist (acceptance)
- [x] Execution fills at bid/ask (not mid) in tests
- [x] Fees reduce PnL correctly in tests
- [x] Latency changes fill timing (test with a simple time shift)
- [x] Slippage cost is accounted as a cost (test numeric correctness)
- [x] Constraints prevent exceeding max exposure (test: strategy tries to overbuy)

---

## 6) Backtest engine v1 (MVP end-to-end) (Day 2–3)

### Tasks
Build the core loop (bar-based):

- For each bar:
  - strategy emits target position or order intent
  - apply latency (if enabled)
  - execute orders and generate fills
  - update positions and cash
  - mark-to-market equity using last price (document method)
- Track:
  - realized PnL
  - unrealized PnL
  - equity curve
  - per-market exposure

### Add 2–3 baseline strategies
- Momentum: buy if return over window > threshold
- Mean reversion: fade large moves
- Event-driven threshold: trade on large price jump or volume spike

### Checklist (acceptance)
- [x] `pm-bt backtest ...` runs end-to-end on fixture data
- [x] Produces:
  - [x] `results.json`
  - [x] `equity.csv`
  - [x] `trades.csv` (fills)
- [x] Unit tests cover PnL accounting on fixture dataset (expected values)
- [x] Strategy interface is clean and documented

---

## 7) Reporting v1 (MVP outputs) (Day 3)

### Tasks
- Export artifacts per run under `output/runs/<run-id>/`:
  - `config.json`
  - `results.json` (including commit hash, runtime, dataset slice)
  - `equity.csv`
  - `fills.csv` (or trades.csv)
- Generate plots (matplotlib only):
  - equity curve
  - drawdown curve
  - distribution of returns (optional)

### Checklist (acceptance)
- [x] Run directory contains all artifacts
- [x] `results.json` includes:
  - [x] run_id
  - [x] strategy name + parameters
  - [x] dataset filters (venue/market/time range)
  - [x] git commit hash
  - [x] runtime breakdown (load/features/execution/report)
- [x] At least 2 plots are generated and saved

---

## 7.5) Prediction-market-specific evaluation (MVP) (Day 3)

### Tasks
- Add resolved-market evaluation:
  - Brier score and/or log loss on comparable prediction snapshots
  - calibration table (predicted probability buckets vs realized frequency)
- Define how predictions are sampled for scoring (close-to-resolution snapshot, bar close, etc.).
- Export PM-specific metrics into `results.json`.

### Checklist (acceptance)
- [x] At least one calibration metric (Brier or log loss) is computed for resolved markets.
- [x] Sampling rule for prediction snapshots is documented and deterministic.
- [x] PM-specific metrics appear in `results.json` and are covered by tests.

---

## 8) Batch runner + tradability metrics (MVP+) (Day 4–6)

### Tasks
- Implement batch mode:
  - select top N markets by volume/liquidity
  - run same strategy across markets
  - aggregate results into a summary table
- Tradability metrics:
  - spread proxy
  - volatility proxy
  - volume and trade frequency
  - slippage proxy (if model supports it)
- Output:
  - `summary.csv` with performance + tradability columns

### Checklist (acceptance)
- [x] `pm-bt batch --top-n 50 ...` runs and outputs `summary.csv`
- [x] Summary contains per-market metrics and ranks markets by performance
- [x] Batch mode is resumable (simple checkpoint file is enough)

---

## 9) Alpha scanner (MVP++) (Week 2)

### Tasks
Build a daily/batch scanner producing alerts:

- Inconsistency checks:
  - mutually exclusive outcomes sum > 1
  - complements (yes/no) not summing close to 1 (within tolerance)
  - implied probability vs linked events (if metadata allows)
- Whale / impact signals:
  - large trade detection relative to rolling volume
  - impact score: price move / size
- Output:
  - `alerts.json` + `alerts.csv`
  - optional: simple HTML report

### Checklist (acceptance)
- [x] Scanner runs on a subset of markets and produces alerts deterministically
- [x] Each alert includes: market_id, time, reason, severity, supporting stats
- [x] False positive rate is controlled by thresholds (configurable)

---

## 10) Prod hardening (Week 2–3)

### Tasks
- Improve reproducibility:
  - strict config schemas (pydantic)
  - version data schema and store it in results
- Improve correctness:
  - more unit tests (fees, slippage, partial fills)
  - golden tests with expected equity curve hash
- Improve performance:
  - profile load + feature steps
  - ensure lazy scans and partition pruning
  - avoid full-materialization unless necessary
- Improve reliability:
  - structured logging
  - better error messages
  - graceful handling of missing data segments

### Checklist (acceptance)
- [x] Coverage >= 70% (target >= 80% later)
- [ ] Golden test passes on CI (equity hash)
- [ ] Basic profiling report exists (README notes runtime on sample)
- [x] `pm-bt` returns non-zero exit code on failures with clear message

---

## 11) Optional: API service (Week 3+)

### Tasks
- FastAPI service:
  - POST `/backtests` with config -> returns run_id
  - GET `/backtests/{run_id}` -> results
  - GET `/backtests/{run_id}/artifacts` -> artifact listing
- Caching:
  - avoid rerunning identical configs on same dataset slice
- Storage:
  - local filesystem first
  - S3/R2 later

### Checklist (acceptance)
- [ ] API can run a backtest and return results
- [ ] Artifacts can be downloaded
- [ ] Docker image builds and runs locally

---

## 12) Optional: Replay UI / Paper trading (Week 3+)

### Tasks
- Market replay view:
  - time slider + speed control
  - trade tape + price chart
- Paper trading:
  - user “buy/sell” in replay mode
  - compare to baseline strategies

### Checklist (acceptance)
- [ ] Replay works for one market end-to-end
- [ ] Paper trades are recorded and shown on the chart
- [ ] Performance summary is displayed

---

## Final “Prod-grade” acceptance checklist

### Quality
- [ ] CI green on main
- [x] Tests cover: bar building, execution (bid/ask), PnL, fees, slippage, latency
- [x] Type checking passes
- [x] Lint passes
- [x] Results are reproducible (config + commit hash)

### Performance
- [ ] Single-market multi-year backtest finishes in seconds on laptop
- [ ] Batch mode runs on N markets without OOM
- [x] Parquet scans use filters and lazy evaluation

### Documentation
- [x] README includes:
  - install
  - how to run 1 backtest
  - how to run batch
  - explanation of execution model assumptions
- [x] `docs/prediction-markets-vs-tradfi.md` explains domain differences and modeling implications
- [x] `SKILLS.md` explains what the project demonstrates
- [x] `docs/` contains data schema notes and strategy interface docs

---

## Suggested naming conventions
- Package: `pm_bt`
- CLI: `pm-bt`
- Run IDs: `YYYYMMDD_HHMMSS_<short-hash>`
- Configs: `configs/<strategy>/<name>.yaml`
