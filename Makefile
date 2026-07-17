.PHONY: setup setup-api setup-web models-download download-real-sample import-real-sample db-up db-down db-status db-up-docker db-down-docker db-migrate seed validate dev-api dev-web lint-api test-api test-web build-web check

PYTHON ?= python3.12
API_VENV := apps/api/.venv
API_PYTHON := $(API_VENV)/bin/python
API_PIP := $(API_VENV)/bin/pip

setup: setup-api setup-web

setup-api:
	$(PYTHON) -m venv $(API_VENV)
	$(API_PIP) install -U pip
	$(API_PIP) install -e "apps/api[dev]"

setup-web:
	pnpm install

models-download:
	$(API_PYTHON) -m app.models_download

download-real-sample:
	@mkdir -p data/raw/ipo-cz-20260620
	@test -f data/raw/ipo-cz-20260620/source.zip || curl -L --fail --max-time 120 -o data/raw/ipo-cz-20260620/source.zip 'https://isdv.upv.gov.cz/doc/opendatast96/tm/OPENDATAST96_TM_CZ_DIFF_20-06-2026_0001.zip'

import-real-sample: download-real-sample
	PYTHONPATH=apps/api $(API_PYTHON) -m app.import_ipo_cz

db-up:
	./scripts/mysql-local.sh start

db-down:
	./scripts/mysql-local.sh stop

db-status:
	./scripts/mysql-local.sh status

db-up-docker:
	docker compose -f infra/compose.yaml up -d mysql

db-down-docker:
	docker compose -f infra/compose.yaml stop mysql

db-migrate:
	cd apps/api && .venv/bin/alembic upgrade head

seed:
	PYTHONPATH=apps/api $(API_PYTHON) -m app.seed

validate:
	$(API_PYTHON) scripts/validate_contracts.py

dev-api:
	$(API_VENV)/bin/uvicorn app.main:app --app-dir apps/api --reload --port 8000

dev-web:
	pnpm --filter @marklens/web dev

test-api:
	cd apps/api && .venv/bin/pytest

test-web:
	pnpm --filter @marklens/web test

lint-api:
	$(API_VENV)/bin/ruff check apps/api packages scripts

build-web:
	pnpm --filter @marklens/web build

check: validate lint-api test-api test-web build-web
