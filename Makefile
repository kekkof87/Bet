PYTHON ?= python3
VENV ?= .venv
ACTIVATE = . $(VENV)/bin/activate

# Root requirements (se presenti)
REQ = requirements.txt

BACKEND_DIR ?= backend/api
FRONTEND_DIR ?= frontend/gui
DATA_DIR ?= data

BACKEND_REQ = $(BACKEND_DIR)/requirements.txt
FRONTEND_REQ = $(FRONTEND_DIR)/requirements.txt

API_PORT ?= 8000
API_URL ?= http://localhost:$(API_PORT)

.PHONY: bootstrap lint type test fetch format clean cov \
        install.backend install.frontend install.all \
        api.run gui.run consensus \
        odds.fetch preds.enrich alerts.gen alerts.dispatch e2e.run \
        roi.run fixtures.snapshot retention.cleanup \
        docker.api.build docker.api.run prom.run help

help:
	@echo "Targets disponibili:"
	@echo "  bootstrap           - venv + install requirements"
	@echo "  api.run             - avvia FastAPI locale (DATA_DIR=$(DATA_DIR))"
	@echo "  gui.run             - avvia Streamlit (API_URL=$(API_URL))"
	@echo "  consensus           - aggrega predictions (sources -> latest_predictions.json)"
	@echo "  odds.fetch          - genera odds (model provider) in $(DATA_DIR)/odds_latest.json"
	@echo "  preds.enrich        - arricchisce predictions con edge/value"
	@echo "  alerts.gen          - genera $(DATA_DIR)/value_alerts.json"
	@echo "  alerts.dispatch     - invia alert via webhook (se impostato)"
	@echo "  e2e.run             - esegue l'intera pipeline locale"
	@echo "  fixtures.snapshot   - materializza fixtures.json da last_delta.json"
	@echo "  roi.run             - calcola ROI (metrics/daily/history)"
	@echo "  retention.cleanup   - rimuove file vecchi (RETENTION_DAYS=$(RETENTION_DAYS))"
	@echo "  docker.api.build/run, prom.run, lint/format/type/test/cov/clean"

bootstrap:
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	@$(ACTIVATE); pip install --upgrade pip
	@if [ -f "$(REQ)" ]; then $(ACTIVATE); pip install -r $(REQ); fi
	@if [ -f "$(BACKEND_REQ)" ]; then $(ACTIVATE); pip install -r $(BACKEND_REQ); fi
	@if [ -f "$(FRONTEND_REQ)" ]; then $(ACTIVATE); pip install -r $(FRONTEND_REQ); fi
	@echo "Bootstrap completato."

install.backend:
	@if [ -f "$(BACKEND_REQ)" ]; then $(ACTIVATE); pip install -r $(BACKEND_REQ); else echo "File non trovato: $(BACKEND_REQ)"; fi

install.frontend:
	@if [ -f "$(FRONTEND_REQ)" ]; then $(ACTIVATE); pip install -r $(FRONTEND_REQ); else echo "File non trovato: $(FRONTEND_REQ)"; fi

install.all: bootstrap install.backend install.frontend

lint:
	@$(ACTIVATE); ruff check .

format:
	@$(ACTIVATE); ruff format .

type:
	@$(ACTIVATE); if [ -f mypy.ini ]; then mypy --config-file mypy.ini --pretty src; else echo "mypy.ini assente"; fi

test:
	@$(ACTIVATE); if [ -d tests ]; then pytest -q; else echo "No tests dir, skipping"; fi

fetch:
	@$(ACTIVATE); PYTHONPATH=src $(PYTHON) scripts/fetch_fixtures.py

cov:
	@$(ACTIVATE); pytest --cov=src --cov-report=term-missing

api.run:
	@$(ACTIVATE); DATA_DIR="$(DATA_DIR)" uvicorn backend.api.main:app --host 0.0.0.0 --port $(API_PORT)

gui.run:
	@$(ACTIVATE); API_URL="$(API_URL)" DATA_DIR="$(DATA_DIR)" streamlit run $(FRONTEND_DIR)/streamlit_app.py

consensus:
	@$(ACTIVATE); PYTHONPATH=. $(PYTHON) scripts/consensus_merge.py \
		--sources-dir "$(DATA_DIR)/predictions/sources" \
		--odds-file "$(DATA_DIR)/odds_latest.json" \
		--out "$(DATA_DIR)/latest_predictions.json" \
		--weights consensus/config.yml \
		--min-models 1

odds.fetch:
	@$(ACTIVATE); ODDS_PROVIDER=$${ODDS_PROVIDER:-model} ENABLE_ODDS_INGESTION=$${ENABLE_ODDS_INGESTION:-1} MODEL_ODDS_MARGIN=$${MODEL_ODDS_MARGIN:-0.0} \
		PYTHONPATH=. $(PYTHON) scripts/fetch_odds.py

preds.enrich:
	@$(ACTIVATE); EFFECTIVE_THRESHOLD=$${EFFECTIVE_THRESHOLD:-0.03} PYTHONPATH=. $(PYTHON) scripts/enrich_predictions.py

alerts.gen:
	@$(ACTIVATE); EFFECTIVE_THRESHOLD=$${EFFECTIVE_THRESHOLD:-0.03} ALERTS_FILTER_STATUS=$${ALERTS_FILTER_STATUS:-} \
		PYTHONPATH=. $(PYTHON) scripts/value_alerts.py

alerts.dispatch:
	@$(ACTIVATE); ALERT_DISPATCH_WEBHOOK=$${ALERT_DISPATCH_WEBHOOK:-} PYTHONPATH=. $(PYTHON) scripts/dispatch_alerts.py

e2e.run:
	@$(MAKE) consensus
	@$(MAKE) odds.fetch
	@$(MAKE) preds.enrich
	@$(MAKE) fixtures.snapshot
	@$(MAKE) roi.run
	@$(MAKE) alerts.gen
	@$(MAKE) alerts.dispatch || true

roi.run:
	@$(ACTIVATE); PYTHONPATH=. $(PYTHON) scripts/roi_compute.py \
		--ledger "$(DATA_DIR)/ledger.jsonl" \
		--out-metrics "$(DATA_DIR)/roi_metrics.json" \
		--out-daily "$(DATA_DIR)/roi_daily.json" \
		--out-history "$(DATA_DIR)/roi_history.jsonl" \
		--append-history

fixtures.snapshot:
	@$(ACTIVATE); PYTHONPATH=. $(PYTHON) scripts/fixtures_snapshot.py \
		--delta-file "$(DATA_DIR)/last_delta.json" \
		--out "$(DATA_DIR)/fixtures.json"

retention.cleanup:
	@$(ACTIVATE); RETENTION_DAYS=$${RETENTION_DAYS:-14} PYTHONPATH=. $(PYTHON) scripts/retention_cleanup.py

docker.api.build:
	docker build -t betting-api -f $(BACKEND_DIR)/Dockerfile .

docker.api.run:
	docker run --rm -p $(API_PORT):8000 -v "$$(pwd)/$(DATA_DIR)":/app/data betting-api

prom.run:
	docker run --rm -p 9090:9090 \
		-v "$$(pwd)/monitoring/prometheus.yml":/etc/prometheus/prometheus.yml \
		-v "$$(pwd)/monitoring/alerts.yml":/etc/prometheus/alerts.yml \
		--name prometheus prom/prometheus

clean:
	@rm -rf $(VENV) __pycache__ .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info data/*.json
