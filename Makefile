PYTHON ?= python3
PIP ?= pip3

VENV ?= .venv
ACTIVATE = . $(VENV)/bin/activate

.PHONY: bootstrap run smoke format lint clean

bootstrap:
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	@$(ACTIVATE); $(PIP) install --upgrade pip
	@$(ACTIVATE); $(PIP) install -r requirements.txt
	@echo "Bootstrap completato."

run:
	@$(ACTIVATE); $(PYTHON) -m src.app

smoke:
	@chmod +x scripts/smoke_test.sh || true
	@$(ACTIVATE); scripts/smoke_test.sh

format:
	@echo "(placeholder) aggiungere black/isort in futuro"

lint:
	@echo "(placeholder) aggiungere ruff/mypy in futuro"

clean:
	@rm -rf $(VENV) __pycache__ .pytest_cache dist build *.egg-info
