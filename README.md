# Bet Data Pipeline (ex “Bet Ingestion Foundation”)

Pipeline incrementale per l’ingestione e l’elaborazione di fixtures di calcio (API-Football), con:
- Fetch con retry/backoff e telemetria
- Normalizzazione e validazione soft delle date
- Diff incrementale (added / removed / modified + classification score/status)
- Persistenza (latest / previous / history rotante)
- Metrics + Delta event + Alerts (score/status transition)
- Scoreboard aggregato
- Predictions baseline (stub probabilità)
- Consensus & ranking (stub)
- API read‑only (FastAPI) per consumo esterno

---

## Quick Start

Se usi `make` (adatta se il nuovo progetto non usa più bootstrap originale):

```
make bootstrap     # opzionale: crea virtualenv e installa dipendenze
make test          # esegue test (alias se definito)
python -m scripts.fetch_fixtures   # esegue il fetch (richiede API_FOOTBALL_KEY)
python -m api.app                  # avvia API su :8000
```

Oppure manuale:

```
pip install -r requirements.txt
export API_FOOTBALL_KEY=...
python -m scripts.fetch_fixtures
python -m api.app
```

---

## Pipeline / Flusso

1. Fetch (retry/backoff) dal provider API-Football
2. Normalizzazione record + validazione soft `date_utc` (flag `valid_date_utc`)
3. Diff incrementale + classification (score_change / status_change / both / other)
4. Persistenza:
   - `fixtures_previous.json`
   - `fixtures_latest.json`
   - snapshot storico (se abilitato)
5. Metrics (`metrics/last_run.json`) + Delta event (`events/last_delta.json`)
6. Alerts (`alerts/last_alerts.json`) su score/status transitions
7. Scoreboard (`scoreboard.json`)
8. Predictions baseline (`predictions/latest_predictions.json`) – stub
9. Consensus & ranking (`consensus/consensus.json`) – stub
10. API read‑only (FastAPI)

---

## Output Principali

| File | Descrizione |
|------|-------------|
| data/fixtures_latest.json | Stato corrente normalizzato |
| data/fixtures_previous.json | Stato precedente |
| data/history/*.json | Snapshot storici (rotazione su HISTORY_MAX) |
| data/metrics/last_run.json | Telemetria ultima run (summary + fetch_stats) |
| data/events/last_delta.json | Ultimo delta non vuoto |
| data/alerts/last_alerts.json | Eventi score_update / status_transition |
| data/scoreboard.json | Aggregato sintetico (live / upcoming / delta counts) |
| data/predictions/latest_predictions.json | Probabilità baseline (se abilitate) |
| data/consensus/consensus.json | Consensus & ranking stub (se abilitato) |

---

## API (FastAPI)

Avvio:
```
python -m api.app  # http://localhost:8000/health
```

| Endpoint | Funzione |
|----------|----------|
| /health | Stato servizio |
| /fixtures | Fixtures correnti (lista) |
| /delta | Ultimo delta + summary |
| /metrics | Snapshot metrics ultima run |
| /scoreboard | Aggregato scoreboard |

Futuri miglioramenti: filtri query (`?status=LIVE`), paginazione, timeframe configurabile.

---

## Diff & Classification

- Compare keys opzionali via `DELTA_COMPARE_KEYS` (es: `home_score,away_score,status`).
- Classification:
  - score_change: cambia uno dei punteggi
  - status_change: cambia solo lo status
  - both: punteggio e status insieme
  - other: altre differenze (se non limitato da compare keys)

Esempio `delta_summary`:
```json
{
  "added": 2,
  "removed": 1,
  "modified": 3,
  "total_new": 120,
  "compare_keys": "home_score,away_score,status"
}
```

---

## Alerts

Generati su:
- Variazione punteggio → `score_update`
- Transizione status forward (sequenza default: NS → 1H → HT → 2H → ET → P → AET → FT) → `status_transition`

File: `alerts/last_alerts.json`

Disabilitazione: `ENABLE_ALERTS_FILE=false`

Personalizzazione:
- `ALERT_STATUS_SEQUENCE` (CSV)
- `ALERT_INCLUDE_FINAL=false` per ignorare FT

---

## Predictions (Baseline Stub)

Caratteristiche:
- Features minime: is_live, score_diff, hours_to_kickoff, status_code
- Probabilità base: home=0.33, draw=0.33, away=0.34 (aggiustate con score_diff)
- File output: `predictions/latest_predictions.json`
- Abilitazione: `ENABLE_PREDICTIONS=1`

---

## Consensus & Ranking (Stub)

- Usa direttamente le probabilità baseline
- `consensus_confidence = max(home_win, draw, away_win)`
- `ranking_score = home_win - away_win`
- File: `consensus/consensus.json`
- Abilitazione: `ENABLE_CONSENSUS=1`

---

## Variabili d’Ambiente Principali

| Variabile | Default | Effetto |
|-----------|---------|---------|
| API_FOOTBALL_KEY | (obbligatoria) | Chiave API-Football |
| BET_DATA_DIR | data | Directory base output |
| API_FOOTBALL_MAX_ATTEMPTS | 5 | Numero tentativi fetch |
| API_FOOTBALL_BACKOFF_BASE | 0.5 | Backoff base (s) |
| API_FOOTBALL_BACKOFF_FACTOR | 2.0 | Fattore crescita backoff |
| API_FOOTBALL_BACKOFF_JITTER | 0.2 | Jitter random |
| API_FOOTBALL_TIMEOUT | 10.0 | Timeout HTTP (s) |
| DELTA_COMPARE_KEYS | (vuoto) | Campi usati per diff |
| FETCH_ABORT_ON_EMPTY | false | Ignora fetch vuoto |
| ENABLE_HISTORY | false | Attiva snapshot storici |
| HISTORY_MAX | 30 | Numero snapshot mantenuti |
| ENABLE_METRICS_FILE | true | Scrive metrics/last_run.json |
| ENABLE_EVENTS_FILE | true | Scrive events/last_delta.json |
| ENABLE_ALERTS_FILE | true | Scrive alerts/last_alerts.json |
| ALERT_STATUS_SEQUENCE | (default interno) | Sequenza status |
| ALERT_INCLUDE_FINAL | true | Includi transizioni verso FT |
| ENABLE_PREDICTIONS | false | Genera predictions baseline |
| PREDICTIONS_DIR | predictions | Cartella predictions |
| MODEL_BASELINE_VERSION | baseline-v1 | Versione modello baseline |
| ENABLE_CONSENSUS | false | Genera consensus |
| CONSENSUS_DIR | consensus | Cartella consensus |

---

## Telemetria Fetch

`fetch_stats` esempio:
```json
{
  "attempts": 1,
  "retries": 0,
  "latency_ms": 123.4,
  "last_status": 200
}
```

---

## Scoreboard

File sintetico `scoreboard.json`:
- total, live_count, upcoming_count_next_24h
- recent_delta (conteggi)
- change_breakdown
- subset `live_fixtures` e `upcoming_next_24h` (limite 10)
- last_fetch_total_new

---

## Struttura Progetto (attuale)

```
scripts/
  fetch_fixtures.py
api/
  app.py
src/
  core/
    config.py
    diff.py
    normalization.py
    persistence.py
    metrics.py
    alerts.py
    scoreboard.py
  providers/
    api_football/
      http_client.py
      fixtures_provider.py
  predictions/
    features.py
    model.py
    pipeline.py
  consensus/
    pipeline.py
tests/
  ... (unit e integrazione)
```

---

## Qualità & CI

- Pytest + coverage (threshold 80% via `--cov-fail-under=80`)
- Ruff (lint)
- mypy (type checking)
- Workflow GitHub Actions:
  - tests / lint / typecheck / coverage
  - fetch (schedule + manual)
- Structured logging JSON

Esempio riga log delta:
```json
{
  "msg": "fixtures_delta",
  "delta_summary": {"added":2,"removed":1,"modified":3,"total_new":120},
  "change_breakdown":{"score_change":2,"status_change":1,"both":0,"other":0},
  "fetch_stats":{"attempts":1,"retries":0,"latency_ms":250.7,"last_status":200}
}
```

---

## Sviluppo

### Test & Lint
```
pytest -q
ruff check .
mypy --pretty src
```

### Esecuzione manuale fetch
```
export API_FOOTBALL_KEY=...
python -m scripts.fetch_fixtures
```

### Avvio API
```
python -m api.app
```

---

## Estendere

### Aggiungere Modello di Predictions Futuro
1. Creare nuovo file in `predictions/` (es. `advanced_model.py`).
2. Integrare in nuova pipeline o aggiornare `run_baseline_predictions`.
3. Salvare in un file distinto (es. `latest_predictions_v2.json`).

### Aggiungere Provider Extra
1. Implementare classe con metodo `fetch_fixtures()`.
2. Integrare in orchestrazione (eventuale step multi-provider futuro).

---

## Roadmap (Prossimi Passi)

| Area | Prossimo Step | Stato |
|------|---------------|-------|
| Alerts Dispatch | Integrazione Telegram / Webhook | TODO |
| Odds Integration | Parsing quote pre‑match | TODO |
| Advanced Predictions | Modelli multipli + feature arricchite | TODO |
| Consensus Evoluto | Pesi dinamici multi-modello | TODO |
| Monitoring | Prometheus /metrics + dashboard Grafana | TODO |
| Storage Analitico | DuckDB / Postgres per query storiche | TODO |
| Telegram Parser | Mapping messaggi live a fixtures | TODO |
| Security | Firma / hash snapshots | TODO |

---

## Contributi

PR incrementali e piccole: preferibile una feature per PR.  
Assicurati che i workflow CI siano verdi prima del merge.

---

## Licenza

TBD (imposta ad esempio MIT se appropriato).

---

## Note Storiche

Il progetto nasce come “Bet Ingestion Foundation” con un loop schedulato mock; evoluto ora in una pipeline strutturata basata su file JSON + API read‑only, per iterare rapidamente prima dell’introduzione di un data store relazionale o colonnare.

---



# MVP Piattaforma Betting

## Requisiti
- Python 3.11+
- (opzionale) Docker

## Struttura
- backend/api: FastAPI read-only su `data/`
- frontend/gui: Streamlit GUI v0 (usa API se `API_URL` è settata, altrimenti file)
- scripts/consensus_merge.py: pipeline consensus/merge
- monitoring/prometheus.yml: scrape config di esempio

## Avvio rapido
```bash
# API
make api.run
# GUI (usa API se API_URL è definita)
make gui.run
# Consensus (aggregazione previsioni multiple)
make consensus
```

Variabili:
- `DATA_DIR`: directory dei file (default: `data/`)
- `API_URL`: per la GUI, es: `http://localhost:8000`

## Docker API
```bash
docker build -t betting-api -f backend/api/Dockerfile .
docker run --rm -p 8000:8000 -v $(pwd)/data:/app/data betting-api
```

## Endpoints
- GET /health
- GET /predictions?min_edge=0.03&active_only=true&status=NS
- GET /odds
- GET /alerts
- GET /fixtures?status=NS
- GET /roi/metrics
- GET /roi/daily
- GET /roi/history
- GET /scoreboard
- GET /delta
- GET /metrics (Prometheus)

Note:
- `/fixtures` legge da `last_delta.json` (chiave `added`) finché non esiste un `fixtures.json` dedicato.
- Il consensus richiede file in `data/predictions/sources/*.json` con campi almeno: `fixture_id`, `market`, `selection` e una probabilità (`prob`/`pred_prob`/`predicted_prob` o `probs[selection]`). Si può adattare in follow-up.


# MVP Piattaforma Betting

## Struttura
- backend/api: FastAPI read-only su `data/`
- frontend/gui: Streamlit GUI v0 (usa API se `API_URL` è settata, altrimenti file)
- scripts/consensus_merge.py: pipeline consensus/merge
- monitoring/: Prometheus + Grafana provisioning e dashboard
- .github/workflows: CI, scheduler

## Avvio rapido (sviluppo)

### Make
```bash
# API
make api.run
# GUI (usa API se API_URL è definita)
make gui.run
# Consensus (aggregazione previsioni multiple)
make consensus
```

### Docker Compose (stack completo)
```bash
cp .env.example .env  # opzionale per credenziali Grafana/porta API
docker compose up --build
# Servizi:
# API:       http://localhost:8000
# GUI:       http://localhost:8501
# Prometheus http://localhost:9090
# Grafana:   http://localhost:3000 (admin/admin se .env non modificato)
```

## Endpoints API
- GET /health
- GET /predictions?min_edge=0.03&active_only=true&status=NS
- GET /odds
- GET /alerts
- GET /fixtures?status=NS
- GET /roi/metrics
- GET /roi/daily
- GET /roi/history
- GET /scoreboard
- GET /delta
- GET /metrics (Prometheus)

Note:
- `/fixtures` legge da `last_delta.json` (chiave `added`) finché non esiste un `fixtures.json` dedicato.
- Il consensus richiede file in `data/predictions/sources/*.json` con campi almeno: `fixture_id`, `market`, `selection` e una probabilità (`prob`/`pred_prob`/`predicted_prob` o `probs[selection]`).

## CI
Workflow `.github/workflows/ci.yml`:
- Lint (ruff), type-check (mypy) e test (pytest) se presenti.
- Build immagine Docker API.
- Publish opzionale su GHCR se `GHCR_PUBLISH=true` tra le repository variables.

## Scheduler dati
Workflow `.github/workflows/schedule.yml`:
- Ogni 30 minuti: esegue eventuale fetch, fa il consensus merge e pubblica gli artifact dei file in `data/`.
- Commit dei dati opzionale se `COMMIT_DATA=true` tra le repository variables.

## Monitoring
- Prometheus scrapa l’API su `/metrics`.
- Grafana preconfigurata con datasource Prometheus e dashboard "API Overview" (RPS, p95 latency, error rate).


# Piattaforma Betting — ROI v1, Polishing, Alerting

Questa PR introduce:
- ROI pipeline v1 (script `scripts/roi_compute.py`, output `data/roi_*.json*`, integrazione GUI)
- Polishing API/GUI (status=NS di default per `/predictions`, `fixtures.json` dedicato, export CSV in GUI)
- Alerting base (metrica `file_age_seconds`, regole Prometheus, dashboard Grafana aggiornata)

## Novità

### ROI pipeline v1
- Script: `scripts/roi_compute.py`
  - Input: `data/ledger.jsonl` (supporta anche `.json` e `.csv`)
  - Output:
    - `data/roi_metrics.json` (totali: profit, yield, hit rate, ecc.)
    - `data/roi_daily.json` (per giorno con `roi` e `cum_profit`)
    - `data/roi_history.jsonl` (append snapshot `--append-history`)
- Makefile:
  - `make roi.run`

### Polishing API/GUI
- API:
  - `/predictions`: default `status=NS` se non specificato
  - `/fixtures`: legge `data/fixtures.json` se presente, fallback a `last_delta.json`
  - Esposizione metrica `file_age_seconds{file=...}` su `/metrics`
- GUI (Streamlit):
  - Default filtro status=NS in “Predictions”
  - Pulsante “Download CSV” su Alerts, Predictions, Fixtures, ROI (metrics/daily/history)

### Alerting base
- Prometheus:
  - `monitoring/prometheus.yml` con `rule_files: /etc/prometheus/alerts.yml`
  - `monitoring/alerts.yml`:
    - `FileStale`: `file_age_seconds > 3600` (5m)
    - `HighErrorRate`: error rate 5xx > 5% (5m)
- Grafana:
  - Dashboard aggiornata “API Overview” con pannello “File age (seconds) by file”

## Utilizzo

### ROI
```bash
make roi.run
```

### Fixtures snapshot
```bash
make fixtures.snapshot
```

### Stack Docker
```bash
docker compose up --build
# API:       http://localhost:8000
# GUI:       http://localhost:8501
# Prometheus http://localhost:9090
# Grafana:   http://localhost:3000 (admin/admin se .env non modificato)
```

## Scheduler (GitHub Actions)
Workflow aggiornato `.github/workflows/schedule.yml`:
- Esegue (se presenti) fetch, consensus, fixtures snapshot, ROI compute
- Pubblica artifact dei file `data/`
- Commit dati opzionale con `COMMIT_DATA=true` (Repository Variables)

## Note
- La GUI effettua export CSV localmente (nessuna dipendenza API).
- I file monitorati per `file_age_seconds` sono configurabili con env `FILES_TO_WATCH` (default: principali file in `data/`).
