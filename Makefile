PYTHON ?= python3
VENV ?= .venv
ACTIVATE = . $(VENV)/bin/activate

# Root requirements (già presenti)
REQ = requirements.txt

# Nuovi percorsi e variabili
BACKEND_DIR ?= backend/api
FRONTEND_DIR ?= frontend/gui
DATA_DIR ?= data

BACKEND_REQ = $(BACKEND_DIR)/requirements.txt
FRONTEND_REQ = $(FRONTEND_DIR)/requirements.txt

API_PORT ?= 8000
API_URL ?= http://localhost:$(API_PORT)

.PHONY: bootstrap lint type test fetch format clean cov \
        install.backend install.frontend install.all \
        api.run gui.run consensus roi.run fixtures.snapshot \
        docker.api.build docker.api.run prom.run help

help:
\t@echo "Targets disponibili:"
\t@echo "  bootstrap          - Crea venv e installa requirements (root + backend + frontend se presenti)"
\t@echo "  install.backend    - Installa solo i requirements del backend"
\t@echo "  install.frontend   - Installa solo i requirements del frontend"
\t@echo "  install.all        - Bootstrap + install backend/frontend"
\t@echo "  api.run            - Avvia FastAPI locale (DATA_DIR=$(DATA_DIR), port=$(API_PORT))"
\t@echo "  gui.run            - Avvia Streamlit (API_URL=$(API_URL) se definito)"
\t@echo "  consensus          - Esegue il merge consensus e scrive in $(DATA_DIR)/latest_predictions.json"
\t@echo "  roi.run            - Calcola ROI (metrics/daily/history) da ledger"
\t@echo "  fixtures.snapshot  - Genera $(DATA_DIR)/fixtures.json da last_delta.json"
\t@echo "  docker.api.build   - Build immagine Docker per l'API"
\t@echo "  docker.api.run     - Run Docker API montando $(DATA_DIR)"
\t@echo "  prom.run           - Avvia Prometheus (docker) con config locale"
\t@echo "  lint/format/type/test/cov/clean - Utility di sviluppo"

bootstrap:
\t@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
\t@$(ACTIVATE); pip install --upgrade pip
\t@if [ -f "$(REQ)" ]; then $(ACTIVATE); pip install -r $(REQ); fi
\t@if [ -f "$(BACKEND_REQ)" ]; then $(ACTIVATE); pip install -r $(BACKEND_REQ); fi
\t@if [ -f "$(FRONTEND_REQ)" ]; then $(ACTIVATE); pip install -r $(FRONTEND_REQ); fi
\t@echo "Bootstrap completato."

install.backend:
\t@if [ -f "$(BACKEND_REQ)" ]; then $(ACTIVATE); pip install -r $(BACKEND_REQ); else echo "File non trovato: $(BACKEND_REQ)"; fi

install.frontend:
\t@if [ -f "$(FRONTEND_REQ)" ]; then $(ACTIVATE); pip install -r $(FRONTEND_REQ); else echo "File non trovato: $(FRONTEND_REQ)"; fi

install.all: bootstrap install.backend install.frontend

lint:
\t@$(ACTIVATE); ruff check .

format:
\t@$(ACTIVATE); ruff format .

type:
\t@$(ACTIVATE); mypy --config-file mypy.ini --pretty src

test:
\t@$(ACTIVATE); pytest -q

fetch:
\t@$(ACTIVATE); PYTHONPATH=src $(PYTHON) scripts/fetch_fixtures.py

cov:
\t@$(ACTIVATE); pytest --cov=src --cov-report=term-missing

api.run:
\t@$(ACTIVATE); DATA_DIR="$(DATA_DIR)" uvicorn backend.api.main:app --host 0.0.0.0 --port $(API_PORT)

gui.run:
\t@$(ACTIVATE); API_URL="$(API_URL)" DATA_DIR="$(DATA_DIR)" streamlit run $(FRONTEND_DIR)/streamlit_app.py

consensus:
\t@$(ACTIVATE); PYTHONPATH=. $(PYTHON) scripts/consensus_merge.py \\
\t\t--sources-dir "$(DATA_DIR)/predictions/sources" \\
\t\t--odds-file "$(DATA_DIR)/odds_latest.json" \\
\t\t--out "$(DATA_DIR)/latest_predictions.json" \\
\t\t--weights consensus/config.yml \\
\t\t--min-models 1

roi.run:
\t@$(ACTIVATE); PYTHONPATH=. $(PYTHON) scripts/roi_compute.py \\
\t\t--ledger "$(DATA_DIR)/ledger.jsonl" \\
\t\t--out-metrics "$(DATA_DIR)/roi_metrics.json" \\
\t\t--out-daily "$(DATA_DIR)/roi_daily.json" \\
\t\t--out-history "$(DATA_DIR)/roi_history.jsonl" \\
\t\t--append-history

fixtures.snapshot:
\t@$(ACTIVATE); PYTHONPATH=. $(PYTHON) scripts/fixtures_snapshot.py \\
\t\t--delta-file "$(DATA_DIR)/last_delta.json" \\
\t\t--out "$(DATA_DIR)/fixtures.json"

docker.api.build:
\tdocker build -t betting-api -f $(BACKEND_DIR)/Dockerfile .

docker.api.run:
\tdocker run --rm -p $(API_PORT):8000 -v "$$(pwd)/$(DATA_DIR)":/app/data betting-api

prom.run:
\tdocker run --rm -p 9090:9090 \\
\t\t-v "$$(pwd)/monitoring/prometheus.yml":/etc/prometheus/prometheus.yml \\
\t\t-v "$$(pwd)/monitoring/alerts.yml":/etc/prometheus/alerts.yml \\
\t\t--name prometheus prom/prometheus

clean:
\t@rm -rf $(VENV) __pycache__ .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info data/*.json
