PYTHON ?= python3
VENV ?= .venv
ACTIVATE = . $(VENV)/bin/activate

REQ = requirements.txt

.PHONY: bootstrap lint type test fetch format clean cov

bootstrap:
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	@$(ACTIVATE); pip install --upgrade pip
	@$(ACTIVATE); pip install -r $(REQ)
	@echo "Bootstrap completato."

lint:
	@$(ACTIVATE); ruff check .

format:
	@$(ACTIVATE); ruff format .

type:
	@$(ACTIVATE); mypy --config-file mypy.ini --pretty src

test:
	@$(ACTIVATE); pytest -q

fetch:
	@$(ACTIVATE); PYTHONPATH=src $(PYTHON) scripts/fetch_fixtures.py

cov:
	@$(ACTIVATE); pytest --cov=src --cov-report=term-missing

clean:
	@rm -rf $(VENV) __pycache__ .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info data/*.json
