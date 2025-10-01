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
9. Odds ingestion (stub)
10. Predictions odds enrichment (opzionale)
11. (Planned) Post-match analytics

## Modules Roadmap
- core/: configuration, logging, persistence, diff (delta logic), models
- providers/: API adapters (API-Football attuale, altri futuri)
- predictions/: feature extraction + baseline model + pipeline
- consensus/: consensus & ranking stub
- telegram/: parsing euristico messaggi (skeleton)
- monitoring/: prometheus exporter
- odds/: odds pipeline & providers stub
- api/: read-only HTTP service (FastAPI)
- scripts/: operazioni manuali (fetch, parse_telegram, exporter, fetch_odds)
- tests/: suite automatizzata

## Data Contracts
- FixtureRecord: fixture_id, league_id, season, date_utc, valid_date_utc, home_team, away_team, status, home_score, away_score, provider
- Delta Output:
  - added: List[FixtureRecord]
  - removed: List[FixtureRecord]
  - modified: List[{old: FixtureRecord, new: FixtureRecord, change_type: str}]
  - change_breakdown: Dict[str,int] (score_change, status_change, both, other)

## Quality & CI
- Ruff (lint)
- mypy (type check)
- Pytest + coverage (≥80%)
- Scheduled fetch GitHub Actions
- Logging JSON strutturato

## Delta Fixtures
### Compare Keys (Configurabile)
`DELTA_COMPARE_KEYS` (es: `home_score,away_score,status`) limita i campi da confrontare. Se non impostato confronto shallow completo.

### Change Classification
- score_change
- status_change
- both
- other (solo se compare_keys non limita)

### Flusso Delta
1. Carica previous
2. Fetch new
3. Abort se vuoto + FETCH_ABORT_ON_EMPTY=1
4. diff + classification
5. Salva previous + latest
6. History opzionale
7. metrics/last_run.json & events/last_delta.json
8. alerts/last_alerts.json
9. scoreboard.json
10. predictions + consensus
11. odds (stub)
12. prometheus update (one-shot)

### Persistenza
| File | Scopo | Trigger |
|------|-------|---------|
| fixtures_latest.json | Stato corrente | Ogni fetch |
| fixtures_previous.json | Stato precedente | Se old esiste |
| history/*timestamp*.json | Snapshot storico | ENABLE_HISTORY=1 |
| metrics/last_run.json | Telemetria run | Ogni fetch |
| events/last_delta.json | Ultimo delta non vuoto | Delta presente |
| alerts/last_alerts.json | Eventi score/status | Se eventi |
| scoreboard.json | Aggregato rapido | Ogni fetch |
| predictions/latest_predictions.json | Probabilità baseline | ENABLE_PREDICTIONS=1 |
| consensus/consensus.json | Consensus stub | ENABLE_CONSENSUS=1 |
| telegram/parsed/last_parsed.json | Eventi Telegram | Parser abilitato |
| odds/odds_latest.json | Quote stub | ENABLE_ODDS_INGESTION=1 |

## Algoritmo Diff (Sintesi)
Indicizzazione per fixture_id (fallback combinazione se necessario). Complessità O(n).

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
ENABLE_HISTORY=1 + HISTORY_MAX (default 30).

## Fetch Stats
attempts, retries, latency_ms, last_status.

## Error Handling Principale
| Scenario | Comportamento |
|----------|---------------|
| API key assente | Abort |
| Salvataggio previous error | Log e continua |
| Salvataggio latest error | Log (stato non avanza) |
| Snapshot corrotto | Warning → [] |
| Diff exception | Delta vuoto loggato |
| Fetch vuoto + abort_on_empty | Stato invariato |

## Retrocompatibilità
Client deprecati rimossi (hardening iterazione 10).

## Alerts
- score_update: variazione punteggio
- status_transition: sequenza NS→1H→HT→2H→ET→P→AET→FT (configurabile)
File: alerts/last_alerts.json

## Predictions (Baseline)
Features base: is_live, score_diff, hours_to_kickoff, status_code  
Output: predictions/latest_predictions.json  
Flag: ENABLE_PREDICTIONS

## Consensus & Ranking (Stub)
- consensus_confidence = max(prob)
- ranking_score = home_win - away_win

## Telegram Parser (Iterazione 11)
Parsing regex euristico (goal / status / score_update).  
File: telegram/parsed/last_parsed.json

## Prometheus Exporter (Iterazione 12)
Metriche: delta counts, change breakdown, fetch stats, scoreboard counts.  
Flags: ENABLE_PROMETHEUS_EXPORTER, PROMETHEUS_PORT.

## Odds Ingestion (Iterazione 13 – Stub)
Flag:
- ENABLE_ODDS_INGESTION
- ODDS_PROVIDER (stub)
- ODDS_DIR
- ODDS_DEFAULT_SOURCE

Stub:
- Genera odds pseudo-random coerenti con score_diff
- Converte in decimal odds
File: odds/odds_latest.json

Evoluzioni:
- API real odds
- Multi-book & margin removal
- Feature enrichment predictions
- Value detection

## Predictions – Odds Enrichment (Iterazione 14)
Se `ENABLE_PREDICTIONS_USE_ODDS=1` e file odds presente:
1. Converte quote → implied probabilities (1/odd)
2. Calcola margin = somma(implied_raw) - 1
3. Normalizza implied
4. Aggiunge blocco `odds` a ciascuna prediction (non altera `prob` modello baseline)

Prediction singola arricchita:
```json
{
  "fixture_id": 101,
  "prob": {"home_win":0.45,"draw":0.30,"away_win":0.25},
  "model_version":"baseline-v1",
  "odds": {
    "odds_original":{"home_win":1.9,"draw":3.5,"away_win":4.0},
    "odds_implied":{"home_win":0.52,"draw":0.28,"away_win":0.20},
    "odds_margin":0.05
  }
}
```

Flag: ENABLE_PREDICTIONS_USE_ODDS

Futuro:
- Blending modello vs implied
- Value detection
- Tracking drift quote

## Estensioni Future (Priorità)
| Idea | Descrizione | Priorità |
|------|-------------|----------|
| Multi-model predictions | Ensemble + calibration | Alta |
| Alert dispatch esterno | Telegram/Webhook | Alta |
| Value detection | Prob_model vs implied odds | Alta |
| Consensus evoluto | Pesi multi-modello + odds | Media |
| DB analitico | DuckDB / Postgres | Media |
| Prometheus label per lega | Metriche segmentate | Media |
| Compression history | Gzip snapshots | Bassa |
| Integrity chain | Firma hash snapshot | Bassa |

## Complessità
Diff O(n); memoria per snapshot e delta.

## Rischi Mitigati
| Rischio | Mitigazione |
|---------|-------------|
| File parziali | Scrittura atomica |
| Crescita history | Rotazione |
| Rumore diff | compare_keys |
| Perdita stato | fetch_abort_on_empty |
| Metriche mancanti | fallback metrics/ delta |
| Odds inconsistenti | Enrichment opzionale |

## API (FastAPI)
| Endpoint | Descrizione |
|----------|-------------|
| /health | Stato base |
| /fixtures | Stato corrente |
| /delta | Ultimo delta |
| /metrics | Ultima run metrics |
| /scoreboard | Aggregato sintetico |

## Sintesi
Pipeline incrementale osservabile: diff + classification + metrics + alerts + scoreboard + predictions + consensus + odds + exporter Prometheus. Pronta per introduzione rapida di value detection, dispatch notifiche e modelli avanzati.