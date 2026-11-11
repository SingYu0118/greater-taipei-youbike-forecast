.PHONY: install test lint collect collect-scheduled collector-status reference sync-r2 dataset features train api frontend

install:
	python3.12 -m venv .venv
	.venv/bin/pip install -e '.[dev,models]'
	cd frontend && npm install

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check src tests

collect:
	.venv/bin/youbike-collect

collect-scheduled:
	.venv/bin/python -m youbike_forecast.collectors.scheduler

collector-status:
	launchctl print gui/$$(id -u)/com.singyu.youbike-collector

reference:
	.venv/bin/youbike-fetch-mrt

sync-r2:
	.venv/bin/youbike-sync-r2

dataset:
	.venv/bin/youbike-build-dataset

features:
	.venv/bin/youbike-build-features

train:
	MPLCONFIGDIR=/tmp/youbike-matplotlib XDG_CACHE_HOME=/tmp/youbike-cache .venv/bin/youbike-train

api:
	.venv/bin/uvicorn youbike_forecast.api.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

