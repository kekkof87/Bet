# Architecture Overview

## Flow (Current Scope)
1. Fetch fixtures (scheduled GitHub Action)
2. Validate & persist (atomic write)
3. Delta computation (added / removed / modified + classification) + snapshot previous
4. (Planned) Telegram parsing
5. (Planned) AI reasoning & prediction synthesis
6. (Planned) Consensus & scoring
7. (Planned) Frontend consumption & dashboards
8. (Planned) Post-match analytics

## Modules Roadmap
- core/: configuration, logging, persistence, diff (delta logic), models / fixture_record
- providers/: API adapters (API-Football attuale, altri futuri)
- telegram/: parsing & normalization (planned)
- ai/: feature engineering & reasoning (planned)
- consensus/: merging signals (planned)
- web/ or frontend/: UI delivery (planned)
- api/: read-only HTTP service (FastAPI)

## Data Contracts
- FixtureRecord (dataclass normalizzata):  
  fixture_id, league_id, season, date_utc, valid_date_utc, home_team, away_team, status, home_score, away_score, provider
- Delta Output (detailed):
  - added: List[FixtureRecord]
  - removed: List[FixtureRecord]
  - modified: List[{old: FixtureRecord, new: FixtureRecord, change_type: str}]
  - change_breakdown: Dict[str,int] (score_change, status_change, both, other)

## Quality & CI
- Lint: Ruff
- Typecheck: mypy
- Test: Pytest
- Coverage workflow
- Scheduled data fetch (GitHub Actions)
- Structured logging JSON (delta_summary, change_breakdown, fetch_stats)

## Delta Fixtures
### Compare Keys (Configurabile)
Se definita la variabile d'ambiente `DELTA_COMPARE_KEYS` (es: `home_score,away_score,status`), il diff considera solo quei campi per determinare se una fixture è “modified”.  
Se non impostata: confronto shallow sull’intero record.

### Change Classification
Il diff avanzato (`diff_fixtures_detailed`) classifica le modifiche:
- score_change: cambia almeno uno tra home_score / away_score
- status_change: cambia solo lo status
- both: cambiano punteggio e status insieme
- other: differenze in campi fuori da punteggio e status (solo se compare_keys non limita)

Logging arricchito:
- delta_summary: {"added": X, "removed": Y, "modified": Z, "total_new": N, ...}
- change_breakdown: {"score_change": a, "status_change": b, "both": c, "other": d}

### Flusso Delta (dettaglio)
1. Carica stato precedente: `old = load_latest_fixtures()`
2. Fetch nuove fixtures → `new`
3. Se `FETCH_ABORT_ON_EMPTY=1` e `new` è vuoto → abort senza salvare
4. Calcola diff/classification: `detailed = diff_fixtures_detailed(old, new, ...)`
5. Se `old` non vuoto → salva previous (`fixtures_previous.json`)
6. Salva latest (`fixtures_latest.json`)
7. (Se `ENABLE_HISTORY=1`) salva snapshot timestamped + rotazione
8. Log JSON strutturato con summary e breakdown
9. Scrive metrics/last_run.json & events/last_delta.json (se delta non vuoto)
10. Genera scoreboard.json

### Persistenza
| File | Scopo | Trigger |
|------|-------|---------|
| fixtures_latest.json | Stato corrente canonicale | Ogni fetch riuscito |
| fixtures_previous.json | Stato precedente immediato | Solo se esisteva un vecchio stato |
| history/fixtures_YYYYmmdd_HHMMSS_micro.json | Snapshot storico (opzionale) | Se ENABLE_HISTORY=1 |
| metrics/last_run.json | Snapshot ultima esecuzione (summary + stats) | Ogni fetch |
| events/last_delta.json | Ultimo delta non vuoto | Fetch con cambi |
| scoreboard.json | Aggregato sintetico per API/UI | Ogni fetch |

### Algoritmo Diff (Sintesi)
- Indicizzazione per chiave primaria preferenziale: `fixture_id`
- Fallback chiave composita: `(league_id, date_utc, home_team, away_team)` (record incompleti scartati)
- added / removed / modified via set difference + confronto shallow (limitato da compare_keys se impostato)
- classification: in base a punteggio e status

### Logging (Esempio)
```
{
  "ts":"2025-01-01T10:00:00Z",
  "level":"INFO",
  "logger":"scripts.fetch_fixtures",
  "msg":"fixtures_delta",
  "delta_summary":{"added":2,"removed":1,"modified":3,"total_new":120,"compare_keys":"home_score,away_score,status"},
  "change_breakdown":{"score_change":2,"status_change":1,"both":0,"other":0},
  "fetch_stats":{"attempts":1,"retries":0,"latency_ms":123.4,"last_status":200}
}
```

### History Snapshots
Abilitati con:
- `ENABLE_HISTORY=1`
- `HISTORY_MAX` (default 30) → rotazione automatica

### Fetch Stats (Telemetria)
Campo `fetch_stats` nel log con:
```
{
  "attempts": <int>,
  "retries": <int>,
  "latency_ms": <float>,
  "last_status": <int | null>
}
```
Derivato dal client con retry/backoff.

## Error Handling (Principali)
| Scenario | Comportamento |
|----------|---------------|
| API key assente | Abort con messaggio |
| Errore I/O salvataggio previous | Log errore, continua |
| Errore I/O salvataggio latest | Log errore (stato non avanza) |
| Snapshot corrotto | Warning, trattato come [] |
| Diff exception | Catturata, logged, delta vuoto |
| Fetch vuoto + abort_on_empty | Stato invariato |

## Retrocompatibilità
- `LATEST_FIXTURES_FILE` statico mantenuto per test.
- Provider legacy ancora presente finché non conclusa migrazione totale.

## Estensioni Future (Prioritized)
| Idea | Descrizione | Priorità |
|------|-------------|----------|
| Alerts (score/status transition) | File events dedicato | Alta |
| Prediction baseline | Prob. stub per modelli futuri | Alta |
| Consensus ranking | Aggregazione multi modello | Media |
| Prometheus / OTEL | Metrics & tracing runtime | Media |
| Filtering endpoints | Parametri query API | Media |
| Model validation ISO stricter | Parser robusto date / timezone | Media |
| Compression history | Riduzione spazio (gzip) | Bassa |

## Complessità
- Diff O(n)
- Memory: copie dict indicizzati + delta

## Rischi Mitigati
| Rischio | Mitigazione |
|---------|-------------|
| Corruzione file | Scrittura atomica |
| Crescita snapshot | Rotazione |
| Rumore modifiche | compare_keys / classification |
| Perdita stato per fetch vuoto | Abort config |

## Integrazione Futura
- Telegram parsing userà classification (score_change) per correlare messaggi.
- AI reasoning potrà processare solo subset modified.
- Dashboard leggerà scoreboard.json + metrics.

## Sintesi
Il layer Delta + Classification + History + Metrics/Event + Scoreboard crea una base incrementale, osservabile e pronta a integrazioni (API, alerting, predictions) senza dipendere da un DB esterno.

### Unified Provider & Fetch Stats
Provider fixtures unificato con:
- Retry/backoff
- Telemetria (attempts, retries, latency_ms, last_status)
- Normalizzazione centralizzata in `core/normalization.py`
Client httpx precedente deprecato.

### Metrics & Events
Se `ENABLE_METRICS_FILE=true` → `metrics/last_run.json`.  
Se `ENABLE_EVENTS_FILE=true` e delta non vuoto → `events/last_delta.json`.

### Validazione date_utc
Regex ISO 8601 semplice → aggiunge `valid_date_utc`. Prima occorrenza non valida → warning singolo.

### Read-Only API
Servizio FastAPI (`api/app.py`) espone:
| Endpoint | Descrizione |
|----------|-------------|
| /health | Stato base |
| /fixtures | Stato corrente |
| /delta | Ultimo delta + summary |
| /metrics | Ultima run metrics |
| /scoreboard | Aggregato sintetico |

Scoreboard include:
- total, live_count, upcoming_count_next_24h
- recent_delta (added/removed/modified)
- change_breakdown
- subset live_fixtures / upcoming_next_24h
- last_fetch_total_new

Futuri miglioramenti:
- Filtri /fixtures?status=LIVE
- Parametri timeframe upcoming
- Paginazione

### Alerts (Nuovo)
Sistema di generazione eventi derivati da modifiche:
- score_update: variazione punteggio (home_score o away_score).
- status_transition: cambio status conforme alla sequenza (default: NS → 1H → HT → 2H → ET → P → AET → FT).  
Se `ALERT_STATUS_SEQUENCE` è definita (lista CSV), sostituisce il default; se `ALERT_INCLUDE_FINAL=false` le transizioni verso FT sono ignorate.

File generato (se eventi presenti e `ENABLE_ALERTS_FILE=true`):
`alerts/last_alerts.json`
```json
{
  "generated_at": "...",
  "events": [
    {"type":"score_update","fixture_id":123,"old_score":"0-0","new_score":"1-0","status":"1H"},
    {"type":"status_transition","fixture_id":123,"from":"NS","to":"1H"}
  ],
  "count": 2
}
```

Logging:
Riga `fixtures_alerts` con `alerts_count`.

Variabili:
- ENABLE_ALERTS_FILE (default true)
- ALERTS_DIR (default alerts)
- ALERT_STATUS_SEQUENCE (opzionale, CSV)
- ALERT_INCLUDE_FINAL (default true)

Integrazione:
Generato in `scripts/fetch_fixtures.py` dopo delta e prima dello scoreboard.

### Predictions (Baseline – Nuovo)
Pipeline iniziale di predizione probabilistica (stub):
- Features: `predictions/features.py` (is_live, score_diff, hours_to_kickoff, status_code)
- Modello: `predictions/model.py` (BaselineModel)
  - Probabilità iniziali: home=0.33, draw=0.33, away=0.34
  - Aggiustamento lineare con score_diff
  - Normalizzazione e bounding min 0.05 (draw min 0.05)
- Pipeline: `predictions/pipeline.py`
  - Output: `predictions/latest_predictions.json`
  - Struttura:
    ```json
    {
      "model_version":"baseline-v1",
      "count": N,
      "predictions": [
        {
          "fixture_id": 123,
          "prob": {"home_win":0.33,"draw":0.33,"away_win":0.34},
          "model_version":"baseline-v1"
        }
      ]
    }
    ```
Abilitazione:
- Variabili:
  - ENABLE_PREDICTIONS (default false)
  - PREDICTIONS_DIR (default predictions)
  - MODEL_BASELINE_VERSION (default baseline-v1)

Integrazione:
- Eseguita alla fine di `scripts/fetch_fixtures.py` (sempre invocata; se disabilitata logga skip).
- Nessuna influenza su delta/scoreboard.

Prossimi passi (futuro):
- Feature arricchite (forma squadre, quote, ranking)
- Modelli multipli (ensemble)
- Consensus su probabilità per feed esterno

### Consensus & Ranking (Stub – Nuovo)
Pipeline di consenso iniziale (stub) che replica direttamente le probabilità baseline e calcola:
- consensus_confidence = max(home_win, draw, away_win)
- ranking_score = home_win - away_win (valore >0 preferenza casa, <0 preferenza trasferta)

File generato:
`consensus/consensus.json`
```json
{
  "generated_at": "...",
  "count": N,
  "model_sources": ["baseline-v1"],
  "entries": [
    {
      "fixture_id": 123,
      "prob": {"home_win":0.33,"draw":0.33,"away_win":0.34},
      "consensus_confidence":0.34,
      "ranking_score":-0.01,
      "model_version":"baseline-v1"
    }
  ]
}
```

Configurazione:
- ENABLE_CONSENSUS (default false)
- CONSENSUS_DIR (default consensus)

Esecuzione:
- Integrata a fine `scripts/fetch_fixtures.py` dopo predictions.
- Se predictions assenti o file mancante → genera payload vuoto (count=0).

### Hardening (Iterazione 10)
Azioni:
- Rimossi file deprecati: `providers/api_football/client.py`, `providers/api_football/base.py`
- Coverage threshold impostata a 80% (`--cov-fail-under=80` + `.coveragerc`)
- Esclusi file non critici dalla coverage (fixture_record, deprecated)
- Consolidato flusso pipeline end-to-end:
  fetch → diff/classification → metrics/events/alerts → scoreboard → predictions → consensus

Prossimi sviluppi possibili:
| Area | Idea | Note |
|------|------|------|
| Monitoring | Prometheus exporter /metrics | Export fetch stats & delta counts |
| Storage | DB (PostgreSQL / DuckDB) | Per analisi storiche avanzate |
| Notifications | Telegram / Webhook | Sugli alerts score/status |
| ML | Modelli multipli / ensemble | Sostituisce baseline |
| Security | Firma snapshot | Integrity chain |
Evoluzioni future:
- Media pesata multi-modello

### Telegram Parser (Skeleton – Iterazione 11)
Funzione: parsing euristico rapido di messaggi Telegram testuali (goal / status / score update).

Approccio attuale:
- Pattern base (regex): GOAL / GOL! / emoji ⚽
- Score detection: regex `(\d+)\s*-\s*(\d+)`
- Status detection: HT, FT, 1H, 2H, ET, AET, P
- Fixture ID: `fixture_id=12345` oppure `fixture id: 12345` oppure numero isolato 5–7 cifre (euristico)
- Classificazione messaggio: goal > status > score_update (in base alla prima condizione che matcha)
- Output file (se ENABLE_TELEGRAM_PARSER=1): `telegram/parsed/last_parsed.json`

Struttura output:
```json
{
  "generated_at": "...",
  "count": N,
  "events": [
    {
      "raw_text": "...",
      "type": "goal|status|score_update",
      "fixture_id": 12345,
      "home_score": 1,
      "away_score": 0,
      "status": "1H",
      "detected_at": "..."
    }
  ]
}
```

Variabili:
- ENABLE_TELEGRAM_PARSER (default false)
- TELEGRAM_RAW_DIR (default telegram/raw)  [placeholder per futuri ingest]
- TELEGRAM_PARSED_DIR (default telegram/parsed)

Esecuzione manuale:
```
ENABLE_TELEGRAM_PARSER=1 python -m scripts.parse_telegram samples/messages.txt
```

Evoluzioni future:
- Normalizzazione nomi squadre e mapping su fixtures correnti
- De-duplicazione basata su hash / timestamp
- Arricchimento con timeline, correlazione con alerts (score_change)
- Pipeline integrata post-fetch
- Filtri su confidenza minima
- Ranking basato su expected value / probabilità calibrate
