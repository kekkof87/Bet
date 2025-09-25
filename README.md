# Bet Ingestion Foundation

Base di partenza per il sistema di ingestione dati (fixtures, odds, ecc.).

## Quick Start

```
make bootstrap     # crea virtualenv e installa dipendenze
make run           # avvia l'app (loop schedulato)
make smoke         # esegue test di fumo
```

Variabili d'ambiente (vedi `.env.example`):

- `LOG_LEVEL` (default INFO)
- `SCHEDULER_INTERVAL_SECONDS` (default 5)
- `PROVIDER_MOCK_ENABLED` (true/false)
- `DRY_RUN=1` (se impostato esegue un solo ciclo e termina)

## Struttura

```
Makefile
requirements.txt
.env.example
migrations/
  0001_init.sql
scripts/
  smoke_test.sh
src/
  app.py
  core/
    contracts.py
  providers/
    __init__.py
    mock_provider.py
    registry.py
  scheduler/
    basic_scheduler.py
```

## Flusso di esecuzione

1. `app.py` carica configurazione ed environment.
2. Registra i provider (per ora solo `MockProvider`).
3. Avvia `BasicScheduler`.
4. Ogni intervallo: invoca tutti i provider e stampa log strutturato (linee `PROVIDER_FETCH_OK`).
5. In modalità `DRY_RUN=1` esegue una sola iterazione e termina (usato dallo smoke test).

## Roadmap (estratto)

- Provider reale (API-Football)
- Strato persistenza (db + repository + migrazioni)
- Health & diagnostics endpoints
- Logging JSON + masking segreti
- Retry / circuit breaker provider
- Notifiche (Telegram / webhook)
- Metrics & analytics base
- Docker + Compose
- CI (lint, test, build image)
- Documentazione architetturale (ARCHITECTURE.md / PROVIDERS.md / SECURITY.md)

## Estendere un Provider

Implementare un oggetto con:
```python
class MyProvider:
    def name(self) -> str: ...
    def fetch_fixtures(self) -> list[dict]: ...
```

Registrarlo:
```python
from providers.registry import ProviderRegistry
ProviderRegistry.add(MyProvider())
```

## Licenza
TBD

## Environment variables

Configure these variables in your local environment (via a `.env` file or shell exports) and in CI as needed:

- `API_FOOTBALL_KEY`: your API-Football key (keep it secret; in GitHub, store it as Actions secret `API_FOOTBALL_KEY`).
- `API_FOOTBALL_PERSIST_FIXTURES` (default: `true`): if `true`, saves the latest fixtures to `data/fixtures_latest.json`.
- `BET_DATA_DIR` (default: `data`): directory where persisted files are written.

## CI Workflows

- Tests (`.github/workflows/tests.yml`)
  - Triggers: on push to `main`, on pull requests, and manually via "Run workflow".
  - Runs `pytest` on Ubuntu with Python 3.11.

- Fetch fixtures (`.github/workflows/fetch-fixtures.yml`)
  - Triggers: daily at 03:00 UTC (05:00 Naples during CEST) and manually via "Run workflow".
  - Inputs: optional `date` in `YYYY-MM-DD`.
  - Requirements: repository Actions secret `API_FOOTBALL_KEY` must be set.
  - Artifacts: uploads `fixtures-latest` containing `data/fixtures_latest.json` when present.
