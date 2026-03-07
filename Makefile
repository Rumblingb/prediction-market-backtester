.PHONY: install install-index lint typecheck test coverage profile-sample setup data-setup index data-index

SOURCE ?= all
MODE ?= all

install:
	uv sync --dev

install-index:
	uv sync --dev --group index

lint:
	uv run ruff check .

typecheck:
	uv run basedpyright

test:
	uv run pytest

coverage:
	uv run pytest --cov=src/pm_bt --cov-report=term-missing

profile-sample:
	uv run python scripts/profile_backtest.py --venue kalshi --strategy momentum --config configs/momentum/default.yaml --data-root data --output-root output/profiling --bar-timeframe 5m

setup: data-setup

data-setup:
	bash scripts/setup_data.sh

index: data-index

data-index: install-index
	uv run python scripts/index_data.py --source "$(SOURCE)" --mode "$(MODE)"
