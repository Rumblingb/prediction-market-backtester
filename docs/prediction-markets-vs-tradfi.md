# Prediction Markets vs Traditional Financial Markets

## Purpose

This project is a **production-grade backtesting and analytics engine** for prediction markets (Polymarket and Kalshi), with UI as an optional layer for control and exploration.
The primary goals are:

- correctness of simulation and accounting
- reproducibility of runs
- performance on large Parquet histories
- clear, defensible modeling assumptions

## Why This Domain Is Different

Prediction markets share some trading mechanics with financial markets, but the payoff model and market behavior are different enough that assumptions must be explicit.

| Topic | Prediction Markets | Traditional Financial Markets |
|---|---|---|
| Payoff | Usually binary settlement (`0` or `1`) at resolution | Open-ended PnL from price path over time |
| Price meaning | Interpreted as implied probability | Asset valuation with many drivers |
| Terminal event | Explicit market resolution determines final payout | Often no single terminal event |
| Liquidity profile | Frequently thin, episodic, event-driven | Often deeper and more continuous |
| Structure | Yes/No or mutually exclusive outcomes | Usually single-asset instruments |
| Evaluation | Profit + calibration quality (Brier/log loss) | Mostly risk-adjusted returns |

## Probability Interpretation (Nuanced)

- Prices should be read as **market-implied probabilities**, not guaranteed "true" probabilities.
- Price-to-probability mapping can deviate because of fees, spread, liquidity constraints, inventory/risk management, and venue microstructure.

## Core Concepts for This Engine

- **Market-implied probability**: treat contract prices as probabilities under explicit market assumptions.
- **Resolution-aware accounting**: model unresolved vs resolved states explicitly.
- **Execution realism**: no naive mid-price fills; include spread, fees, slippage, and latency.
- **Tradability constraints**: thin liquidity requires conservative position and exposure controls.
- **Reproducibility**: every run stores config, dataset slice, commit hash, and artifacts.
- **Venue/era-aware market structure**: execution assumptions can differ for CLOB-style and AMM-style periods.

## Backtesting Implications

1. Strategy signals must be evaluated with both financial and probabilistic lenses.
2. PnL alone is insufficient on resolved markets; include calibration metrics:
   - Brier score
   - log loss
3. Market consistency checks can become alpha/risk signals:
   - complementary outcomes deviating from ~1
   - mutually exclusive outcomes summing above plausible bounds
4. Slippage and fill assumptions must be more conservative than in highly liquid TradFi instruments.
5. **Forecasting metrics are not trading performance**:
   - calibration (Brier/log loss) measures predictive quality on resolved markets
   - PnL measures executable performance under microstructure constraints

## Current Simulator Assumptions

These are the assumptions implemented today in `pm_bt`, not generic future goals.

- **Payoff semantics**: exposure limits are computed in **cash-at-risk** terms for binary payoff
  contracts, rather than in raw notional.
- **Fill side**: buys fill at `ask = mid + spread / 2`; sells fill at
  `bid = mid - spread / 2`.
- **Spread proxy**: the simulator defaults to a `0.02` spread when the snapshot does not provide a
  spread or recent trade prices. In the current backtest engine, bar snapshots do not yet pass
  recent prices, so the default spread proxy is what the standard CLI path uses.
- **Slippage**: slippage is applied on top of bid/ask. The active configuration exposed through
  `BacktestConfig` is basis-point slippage on fill price.
- **Fees**: fees are modeled as a percent of filled notional.
- **Latency**: orders are queued and activated after `latency_bars`; latency is therefore modeled
  in whole-bar units in the current engine.
- **Liquidity model**: there is no order-book depth or venue queue model yet. Orders fill in full
  once eligible unless risk limits clip the requested quantity.
- **Marking method**: equity and unrealized PnL are marked using the latest bar close / last trade
  proxy tracked by the engine.
- **Calibration sampling rule**: prediction-quality metrics are computed from **fill execution
  prices** joined to resolved market outcomes, not from near-resolution snapshots.

These assumptions are conservative enough for MVP work, but they should still be read as explicit
modeling choices rather than venue-perfect microstructure replication.

## Vocabulary Guardrails

Use domain-native language:

- implied probability
- binary payoff
- market resolution
- outcome token
- calibration
- market consistency

Avoid blindly porting terms or assumptions from equities/FX/macro without mapping them to prediction-market mechanics.

## MVP Scope Alignment

For MVP, focus on 1–2 themes/markets end-to-end:

- load Parquet efficiently (lazy scans + pushdown)
- build bars and baseline strategies
- run execution-aware backtests with risk constraints
- generate reproducible artifacts and core metrics
- include resolved-market calibration metrics

This produces a credible artifact that demonstrates systems, performance, and quant engineering skills in the correct market context.
