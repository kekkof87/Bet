# Pipeline end-to-end (fixtures → odds → predictions → ROI)

## Variabili chiave
- PROVIDER_SOURCE: `fd` (football-data) oppure `api` (API-Football).
- FOOTBALL_DATA_API_KEY: secret richiesto per provider `fd`.
- ENABLE_ODDS_INGESTION=1, ODDS_PROVIDER=`model` oppure `stub`.
- ENABLE_PREDICTIONS=1, ENABLE_PREDICTIONS_USE_ODDS=1, ENABLE_VALUE_DETECTION=1.
- ENABLE_ROI_TRACKING=1 (+ eventuali flag ROI desiderati, vedi `core/config.py`).

## Flusso
1. `scripts/fetch_fixtures.py`
2. `scripts/fetch_odds.py`
3. `scripts/run_predictions.py`
4. `scripts/update_roi.py`

I file chiave generati:
- `data/fixtures_latest.json`
- `data/odds/odds_latest.json`
- `data/predictions/latest_predictions.json`
- `data/roi/roi_metrics.json` (+ ledger e csv)

## Note
- In CI, per evitare fallback “ALL LEAGUES” nei test, lasciare `FETCH_ABORT_ON_EMPTY=1` (come da PR precedente).
- Per produzione, abilita esplicitamente `ALLOW_ALL_LEAGUES_FALLBACK=1` solo se realmente necessario.
