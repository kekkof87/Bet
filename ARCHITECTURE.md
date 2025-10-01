# Architecture Overview

## Flow (Current Scope)
1. Fetch fixtures (scheduled GitHub Action)
2. Validate & persist (atomic write)
3. Delta computation (added / removed / modified + classification) + snapshot previous
4. Telegram parsing (skeleton – opzionale se abilitato)
5. Predictions baseline (stub)
6. Consensus & ranking (stub)
7. Scoreboard & API read-only
8. Prometheus exporter (opzionale)
9. (Planned) Post-match analytics

## Modules Roadmap
- core/: configuration, logging, persistence, diff (delta logic), models
- providers/: API adapters (API-Football attuale, altri futuri)
- predictions/: feature extraction + baseline model + pipeline
- consensus/: consensus & ranking stub
- telegram/: parsing euristico messaggi (skeleton)
- monitoring/: prometheus exporter
- api/: read-only HTTP service (FastAPI)
- scripts/: operazioni manuali (fetch, parse_telegram, exporter)
- tests/: suite automatizzata

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
- Test: Pytest (+ coverage soglia 80%)
- Coverage workflow
- Scheduled data fetch (GitHub Actions)
- Structured logging JSON (delta_summary, change_breakdown, fetch_stats)

## Delta Fixtures
### Compare Keys (Configurabile)
Se definita `DELTA_COMPARE_KEYS` (es: `home_score,away_score,status`), il diff considera solo quei campi per determinare se una fixture è “modified”.  
Se non impostata: confronto shallow sull’intero record.

### Change Classification
- score_change: cambia almeno uno tra home_score / away_score
- status_change: cambia solo lo status
- both: cambiano punteggio e status insieme
- other: differenze in campi fuori punteggio/status (solo se compare_keys non limita)

### Flusso Delta
1. Carica previous (fixtures_latest se presente)
2. Fetch nuove fixtures
3. Abort opzionale se vuoto + FETCH_ABORT_ON_EMPTY=1
4. diff_fixtures_detailed
5. Salvataggio previous + latest
6. History (se abilitato)
7. metrics/last_run.json & events/last_delta.json
8. alerts/last_alerts.json (score/status)
9. scoreboard.json
10. predictions + consensus
11. update Prometheus (one-shot)

### Persistenza
| File | Scopo | Trigger |
|------|-------|---------|
| fixtures_latest.json | Stato corrente | Ogni fetch |
| fixtures_previous.json | Stato precedente | Se esisteva old |
| history/*timestamp*.json | Snapshot storico | ENABLE_HISTORY=1 |
| metrics/last_run.json | Telemetria run | Ogni fetch |
| events/last_delta.json | Ultimo delta non vuoto | Fetch con modifiche |
| alerts/last_alerts.json | Eventi score/status | Se eventi generati |
| scoreboard.json | Aggregato rapido | Ogni fetch |
| predictions/latest_predictions.json | Probabilità baseline | Se ENABLE_PREDICTIONS=1 |
| consensus/consensus.json | Consensus stub | Se ENABLE_CONSENSUS=1 |
| telegram/parsed/last_parsed.json | Eventi Telegram parse | Se parser + flag abilitati |

## Algoritmo Diff (Sintesi)
Indicizzazione primaria per fixture_id; fallback (league_id, date_utc, home_team, away_team) se mancano campi. O(n) su numero fixtures.

## Logging (Esempio)
```json
{
  "msg":"fixtures_delta",
  "delta_summary":{"added":2,"removed":1,"modified":3,"total_new":120,"compare_keys":"home_score,away_score,status"},
  "change_breakdown":{"score_change":2,"status_change":1,"both":0,"other":0},
  "fetch_stats":{"attempts":1,"retries":0,"latency_ms":123.4,"last_status":200}
}
```

## History
ENABLE_HISTORY=1 + HISTORY_MAX (default 30) → rotazione su numero massimo snapshot.

## Fetch Stats
`fetch_stats`: attempts, retries, latency_ms, last_status.

## Error Handling Principale
| Scenario | Comportamento |
|----------|---------------|
| API key assente | Abort con messaggio |
| Salvataggio previous error | Log errore, continua |
| Salvataggio latest error | Log errore, stato non avanza |
| Snapshot corrotto | Warning → trattato come [] |
| Eccezione diff | Delta vuoto + log |
| Fetch vuoto + abort_on_empty | Stato invariato |

## Retrocompatibilità
Vecchi client deprecati rimossi (hardening iterazione 10).

## Alerts
Regole:
- score_update: variazione punteggio
- status_transition: status segue sequenza (default NS→1H→HT→2H→ET→P→AET→FT)
Configurabili con ALERT_STATUS_SEQUENCE e ALERT_INCLUDE_FINAL.

Output: `alerts/last_alerts.json`

## Predictions (Baseline)
- Features: is_live, score_diff, hours_to_kickoff, status_code
- Modello semplice lineare + clamp
- Output: predictions/latest_predictions.json
- Flag: ENABLE_PREDICTIONS

## Consensus & Ranking (Stub)
Replica baseline:
- consensus_confidence = max(prob)
- ranking_score = home_win - away_win
Output: consensus/consensus.json

## Hardening (Iterazione 10)
- Rimozione file deprecati
- Soglia coverage 80%
- Esclusioni coverage (.coveragerc)
- Pipeline end-to-end stabilizzata

## Telegram Parser (Iterazione 11)
Parsing euristico:
- Goal pattern: GOAL / GOL! / ⚽
- Score regex: `(\d+)\s*-\s*(\d+)`
- Status: HT, FT, 1H, 2H, ET, AET, P
- Fixture ID: pattern fixture_id= / fixture id: / numero 5–7 cifre
Output (flag ENABLE_TELEGRAM_PARSER): `telegram/parsed/last_parsed.json`

## Prometheus Exporter (Iterazione 12)
Flag:
- ENABLE_PROMETHEUS_EXPORTER
- PROMETHEUS_PORT (default 9100)

Metriche:
- bet_fetch_runs_total
- bet_fixtures_total
- bet_delta_added / removed / modified
- bet_change_score / status / both / other
- bet_fetch_latency_ms / retries / attempts
- bet_scoreboard_live / bet_scoreboard_upcoming_24h

Aggiornamento:
- One-shot in fetch script
- Loop server: `python -m scripts.run_prometheus_exporter`

Evoluzioni future:
- Accuratezza predictions
- Serie temporali delta
- Health timestamp

## Estensioni Future (Priorità)
| Idea | Descrizione | Priorità |
|------|-------------|----------|
| Multi-model predictions | Ensemble + calibration | Alta |
| Odds ingestion | Arricchire features | Alta |
| Alert dispatch esterno | Telegram/Webhook | Alta |
| DB analitico | DuckDB/Postgres | Media |
| Prometheus avanzato | Label per league / season | Media |
| Compression history | Gzip snapshots | Bassa |
| Integrity chain | Firma hash snapshot | Bassa |

## Complessità
Diff O(n). Memoria: dizionari indicizzati + delta struct.

## Rischi Mitigati
| Rischio | Mitigazione |
|---------|-------------|
| File parziali | Scrittura atomica |
| Crescita history | Rotazione |
| Rumore diff | compare_keys |
| Stato perso su fetch vuoto | fetch_abort_on_empty |
| Metriche mancanti | fallback metrics->delta |

## API (FastAPI)
| Endpoint | Descrizione |
|----------|-------------|
| /health | Stato base |
| /fixtures | Stato corrente |
| /delta | Ultimo delta + summary |
| /metrics | Ultima run metrics |
| /scoreboard | Aggregato sintetico |

## Sintesi
Pipeline incrementale osservabile: diff + classification + metrics + alerts + scoreboard + predictions + consensus + esportazione Prometheus, pronta a evoluzioni (odds, ensemble, notifiche).