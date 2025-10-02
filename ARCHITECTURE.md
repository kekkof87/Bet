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

### Alert Dispatch (Iterazione 15 – Stub)
Funzione: invio rapido degli eventi alerts (score/status) verso canali esterni.

Flag:
- ENABLE_ALERT_DISPATCH (default false)
- ALERT_DISPATCH_MODE=stdout|webhook|telegram (default stdout)
- ALERT_WEBHOOK_URL (se mode=webhook)
- ALERT_TELEGRAM_BOT_TOKEN / ALERT_TELEGRAM_CHAT_ID (se mode=telegram)

Flusso:
1. Generazione alerts (alerts/last_alerts.json)
2. Dispatch manuale: `python -m scripts.dispatch_alerts`
3. (Opzionale) Hook automatico in fetch script dopo write_alerts

Formati:
- stdout: log line per evento
- webhook: POST JSON {dispatched_at, count, events}
- telegram: invio singolo messaggio per evento (sendMessage)

Evoluzioni:
- Batch Telegram unico
- Rate limit / deduplica
- Retry con backoff
- Template formattazione messaggi
Pipeline incrementale osservabile: diff + classification + metrics + alerts + scoreboard + 
predictions + consensus + odds + exporter Prometheus. Pronta per introduzione rapida di value detection, dispatch notifiche e modelli avanzati.

### Value Detection (Iterazione 16 – Stub)
Scopo: primo segnale di “value” confrontando probabilità modello vs implied odds.

Logica:
- delta_esito = p_model_esito - p_implied_esito
- value_side = esito con delta massimo
- value_edge = delta massimo
- Attivo solo se value_edge >= VALUE_MIN_EDGE
- adjusted_edge (opzionale) = value_edge * (1 + odds_margin)

Flag:
- ENABLE_VALUE_DETECTION (default false)
- VALUE_MIN_EDGE (default 0.05)
- VALUE_INCLUDE_ADJUSTED (default true)

Output prediction:
```json
{
  "fixture_id": 123,
  "prob": {...},
  "odds": {...},
  "value": {
    "active": true,
    "value_side": "home_win",
    "value_edge": 0.07,
    "adjusted_edge": 0.0735,
    "deltas": {"home_win":0.07,"draw":-0.02,"away_win":-0.05}
  }
}
```

Evoluzioni future:
- Filtri per priorità segnale
- Notifiche automatiche high-value
- Integrazione consensus (pesi value)
- Backtesting ROI vs edge

### Predictions API (Iterazione 17)
Endpoint: GET /predictions  
Sorgente: predictions/latest_predictions.json

Query params:
- value_only (bool) → solo predictions con value.active true
- min_edge (float) → soglia minima su value_edge (applica filtro, esclude predictions senza value)
- limit (int) → max elementi (1–500)

Ordinamento:
- Se value_only o min_edge attivi: per value_edge desc
- Altrimenti: fixture_id asc

Response:
{
  "model_version": "...",
  "count": N,
  "total_available": M,
  "value_only": false,
  "min_edge": 0.05,
  "value_filtered": true,
  "items": [ ... predictions ... ]
}

Use cases:
- Dashboard filtraggio rapido segnali value
- Paginazione futura (limit + offset da aggiungere in evoluzione)
- Estensioni: filtro per status, live-only, range date

Evoluzioni Future:
- /predictions/value (solo summary)
- Aggregazione su margini e distribuzione edge
- Caching in memoria

### Consensus v2 (Iterazione 18)
Blending tra probabilità baseline e odds implied.

Configurazione:
- ENABLE_CONSENSUS
- CONSENSUS_BASELINE_WEIGHT (default 0.6) → peso del modello baseline; 1-peso applicato a implied odds.

Per ogni prediction:
- blended_prob: w * prob_model + (1-w) * odds_implied (normalizzato)
- consensus_confidence: max(blended_prob)
- ranking_score: blended_home_win - blended_away_win
- consensus_value (se odds presenti):
  - deltas = blended - odds_implied
  - value_side = esito con delta max
  - value_edge = delta max
  - active = value_edge > 0

File: consensus/consensus.json
```json
{
  "count": N,
  "baseline_weight": 0.6,
  "entries": [
    {
      "fixture_id": 123,
      "blended_prob": {"home_win":0.45,"draw":0.30,"away_win":0.25},
      "consensus_confidence":0.45,
      "ranking_score":0.20,
      "consensus_value":{
        "active":true,
        "value_side":"home_win",
        "value_edge":0.03,
        "deltas":{"home_win":0.03,"draw":-0.01,"away_win":-0.02}
      }
    }
  ]
}
```

Evoluzioni:
- Ponderazioni dinamiche per status (live vs pre-match)
- Aggiunta modello avanzato (ensemble multi-sorgente)
- Integrazione value detection globale vs consensus_value

### Value Alerts (Iterazione 19)
Obiettivo: estrarre segnali di "value" attivi da predictions (value.active) e consensus (consensus_value.active) producendo un file unificato.

Flag:
- ENABLE_VALUE_ALERTS (default false)
- VALUE_ALERTS_DIR (default value_alerts)

File: value_alerts/value_alerts.json
```json
{
  "count": N,
  "alerts": [
    {
      "source": "prediction|consensus",
      "value_type": "prediction_value|consensus_value",
      "fixture_id": 123,
      "value_side": "home_win",
      "value_edge": 0.07,
      "deltas": {...}
    }
  ]
}
```

Dispatch opzionale:
Riutilizza notifications.dispatcher convertendo gli alert in eventi `type=value_alert`.

Evoluzioni:
- Soglia edge minima configurabile dedicata
- Raggruppamento per partita
- Notifica combinata (prediction + consensus)

### Consensus API (Iterazione 19)
Endpoint: GET /consensus

Filtri:
- min_confidence
- min_value_edge
- value_only
- limit

Ordinamento:
- Se filtro value attivo: per value_edge desc
- Altrimenti: fixture_id asc

Preparazione a dashboard ranking + watchlist.

### Value Alerts API (Iterazione 20)
Endpoint: GET /value_alerts

Origine: value_alerts/value_alerts.json generato da pipeline (prediction + consensus).

Filtri:
- source=prediction|consensus (ripetibile)
- min_edge (>=0)
- limit (1–500)

Ordinamento:
- Se min_edge presente: value_edge desc
- Altrimenti: fixture_id asc + source

Response:
{
  "count": N,
  "total_available": M,
  "filters": {"sources": [], "min_edge": null, "limit": null},
  "items": [...],
  "value_filter_applied": bool
}

Evoluzioni future:
- Aggiunta timestamp generazione per alert
- Dedup per fixture (merge prediction + consensus)
- Segmentazione live/pre-match

### Value History (Iterazione 21)
Scopo: registrare append-only degli edge di value (prediction + consensus) per analisi storiche.

Flag:
- ENABLE_VALUE_HISTORY (default false)
- VALUE_HISTORY_DIR (default value_history)
- VALUE_HISTORY_MAX_FILES (default 30, solo per rolling)
- VALUE_HISTORY_MODE: daily | rolling (default daily)

Modalità:
- daily: un file JSONL per giorno (timestamp UTC), append continuo.
- rolling: un file JSONL per ogni run, rotazione per numero massimo file.

Record JSONL:
{"ts":"2025-10-01T12:00:00.000000+00:00","fixture_id":123,"source":"prediction","value_type":"prediction_value","value_side":"home_win","value_edge":0.07,"model_version":"baseline-v1"}

Evoluzioni:
- Aggregatore giornaliero (edge stats, distribuzioni)
- Persist DB / DataLake
- Filtri live-only / pre-match separati
- Integrazione con ROI tracking (post-match outcome)

### Model Adjust (Iterazione 22)
Blending diretto delle probabilità baseline con le implied odds all’interno delle predictions.

Flag:
- ENABLE_MODEL_ADJUST (default false)
- MODEL_ADJUST_WEIGHT (default 0.7, clamp [0,1]) = peso baseline (1-w mercato)

Per prediction (se odds disponibili e flag attivo):
- prob_adjusted: probabilità ricalcolate
- prob invariato (baseline puro)
- value detection resta basata su prob baseline (next step: versione su adjusted se necessario)

Formula:
p_adj = w * p_model + (1 - w) * p_implied → normalizzazione → round(6)

Motivazioni:
- Evita drift eccessivo delle quote quando il modello è stabile.
- Passo intermedio prima di calibration più sofisticata (Platt / isotonic / bayes blending).

Future evoluzioni:
- Dynamic weight: diverso se live vs pre-match
- Confidence factor (varianza modello → peso)
- Adjust pipeline su consensus invece che singolo modello
=======
- Integrazione con ROI tracking (post-match outcome)

### ROI Tracking (Iterazione 23 – Stub)
Scopo: simulare strategia elementare basata su value alerts per calcolo profit/loss cumulato.

Configurazione:
- ENABLE_ROI_TRACKING (default false)
- ROI_DIR (default roi)
- ROI_MIN_EDGE (default 0.05)
- ROI_INCLUDE_CONSENSUS (default true)
- ROI_STAKE_UNITS (default 1.0)

Logica:
1. Carica value_alerts.json
2. Filtra alert attivi con edge >= ROI_MIN_EDGE
3. Genera pick solo se:
   - fixture status = NS
   - nessuna pick esistente per (fixture_id, source)
4. Ogni pick: stake fisso (ROI_STAKE_UNITS), est_odds stimata (stub 2.0 baseline – evoluzione leggendo odds reali)
5. Settlement:
   - Quando fixture passa a FT
   - outcome: home_win / draw / away_win da punteggio finale
   - profit pick win: (est_odds - 1) * stake
   - loss: -stake
6. Ledger: roi/ledger.json
7. Metriche aggregate: roi/roi_metrics.json
   - total_picks, settled_picks, open_picks
   - wins, losses
   - profit_units
   - yield (profit / somma stake)
   - hit_rate (wins / settled)
8. Integrazione fetch: dopo value alerts (quindi picks possono vedere status aggiornato).

Evoluzioni future:
- Uso odds reali (decimal) per payout più credibile
- Multi-stake (Kelly / Edge weighted)
- Esclusione consensus o pesi separati
- ROI segmentato per source / month / league
- Dashboard trending curve

### ROI Real Odds & API (Iterazione 24)

Aggiornamenti:
1. ROI con odds reali:
   - Recupero decimal odds prioritario:
     a) odds_latest.json -> entries[].market[esito]
     b) predictions/latest_predictions.json -> prediction.odds.odds_original[esito]
     c) fallback 2.0
   - Campi pick:
     {
       "fixture_id": ...,
       "source": "prediction|consensus",
       "side": "...",
       "edge": 0.07,
       "stake": 1.0,
       "decimal_odds": 2.25,
       "est_odds": 2.25,          (backward compatibility)
       "fair_prob": 0.444444,
       "odds_source": "odds_latest|predictions_odds|fallback",
       "settled": false
     }

2. Settlement:
   - outcome derivato da (home_score, away_score).
   - profit se win = (decimal_odds - 1) * stake.
   - Altrimenti -stake (gestito come payout=0 e calcolo in aggregato).

3. ROI API /roi:
   Parametri:
   - detail (bool) -> includi/le pick
   - source= (ripetibile) filtra (prediction, consensus)
   - open_only (bool)
   - limit (int, max 1000)
   Output:
   {
     "enabled": true,
     "metrics": {...},
     "items": [...],
     "filters": {...},
     "detail_included": true|false
   }

4. File scritti:
   - roi/ledger.json
   - roi/roi_metrics.json

5. Evoluzioni Possibili:
   - Storage odds reali specifiche del pick al momento della creazione (snapshot vs latest).
   - Odds drift tracking.
   - Stake dinamico (Kelly / Edge scaling).
   - Filtri orari (solo pre-match > X minuti all’avvio).

---

### Guida Semplice: Come Aggiungere/Migliorare l’Uso delle Odds Reali

1. Fonte odds (odds_latest.json):
   - Generato dalla pipeline odds (run_odds_pipeline).
   - Struttura: {"entries":[{"fixture_id":123,"market":{"home_win":2.1,"draw":3.3,"away_win":3.4}, ...}]}

2. Arricchimento predictions:
   - Durante run_baseline_predictions, se presenti odds_latest.json e ENABLE_PREDICTIONS_USE_ODDS=1:
     - calcola implied (p = 1/odds normalizzate).
     - salva in prediction.odds.odds_original (decimal) e odds.odds_implied (prob).

3. Value detection:
   - Usa differenza model vs implied (pred.prob vs odds_implied).
   - Attiva con ENABLE_VALUE_DETECTION.

4. Value alerts:
   - build_value_alerts legge prediction.value (active) e consensus.consensus_value (active).
   - Genera value_alerts.json.

5. ROI picks:
   - Per ogni alert eligible:
     a) Legge status fixture (NS richiesto).
     b) edge >= ROI_MIN_EDGE.
     c) Cerca odds in odds_latest.json (priorità).
     d) Se non trova, cerca prediction.odds.odds_original.
     e) Se ancora niente, fallback 2.0.

6. Controllo rapido:
   - Esegui l’intera pipeline (script fetch).
   - Verifica file:
     data/odds/odds_latest.json
     data/predictions/latest_predictions.json
     data/value_alerts/value_alerts.json
     data/roi/ledger.json

7. Debug se le picks mostrano decimal_odds=2.0 (fallback):
   - Assicurati che l’esito (home_win/draw/away_win) sia presente come key in market.
   - Controlla che fixture_id combaci (numeri coerenti).
   - Verifica che run_odds_pipeline sia stato eseguito prima di run_baseline_predictions (ordine già adeguato nello script).

8. Estensioni future (facili):
   - Salvare nel pick anche "market_snapshot": copia del blocco market per audit.
   - Calcolare implied_margin per valutare qualità bookmaker (sum(1/odds)-1).
   - Integrare odds live (nuovo file es: odds_live.json).

---

Questa iterazione sblocca:
- Profit tracking più realistico.
- Esposizione rapida via API per dashboard o grafici esterni.

### ROI Timeline (Iterazione 25)
Obiettivo: tracciare evoluzione temporale delle metriche ROI per analisi storica e grafici.

Flag:
- ENABLE_ROI_TIMELINE (default true)
- ROI_TIMELINE_FILE (default roi_history.jsonl)
- ROI_DAILY_FILE (default roi_daily.json)

File:
- roi_history.jsonl: append-only, un record per run
  Esempio linea:
  {"ts":"2025-10-01T12:00:00.000000+00:00","total_picks":12,"settled_picks":9,"profit_units":2.3,"yield":0.085,"hit_rate":0.5556}

- roi_daily.json: aggregazione per giorno UTC
  {
    "2025-10-01": {
       "last_ts":"2025-10-01T12:05:00Z",
       "runs":5,
       "total_picks":12,
       "settled_picks":9,
       "profit_units":2.3,
       "yield":0.085,
       "hit_rate":0.5556
    }
  }

Aggancio:
- build_or_update_roi() dopo salvataggio metrics → _append_timeline()

Evoluzioni future:
- Rolling window (7d, 30d) calcolata automaticamente
- Endpoint /roi/timeline con slicing temporale
- CSV export per BI


### Value Alerts Dedicated Threshold (Iterazione 26)

Motivazione:
Separare la soglia di attivazione della rilevazione value (VALUE_MIN_EDGE) dalla soglia di pubblicazione degli alert (VALUE_ALERT_MIN_EDGE).  
Consente di:
- Mantenere detection “larga” per analisi interne.
- Ridurre rumore negli alerts e nelle pipeline che li consumano (ROI, dispatch).

Variabili:
- VALUE_MIN_EDGE (già esistente): soglia minima perché un “value” sia marcato active all’interno di predictions/consensus.
- VALUE_ALERT_MIN_EDGE (nuova): soglia minima per includere l’elemento in value_alerts.json (default = VALUE_MIN_EDGE se non definita).

Implementazione:
1. Aggiunto campo `value_alert_min_edge` in Settings, parse da env `VALUE_ALERT_MIN_EDGE` (fallback: value_min_edge).
2. In `predictions/value_alerts.py` filtraggio: edge < value_alert_min_edge → skip.
3. Aggiunto campo `threshold_edge` nel file `value_alerts.json` per audit.

Effetti su pipeline:
- ROI tracking legge value_alerts.json → numero picks ridotto se la soglia è maggiore.
- Nessuna modifica a value detection interna (prob + implied).

Test:
- test_value_alert_threshold.py verifica esclusione/inclusione rispetto alla soglia.

Evoluzioni possibili:
- Soglie separate per prediction vs consensus (es: VALUE_ALERT_MIN_EDGE_PRED, VALUE_ALERT_MIN_EDGE_CONS).
- Finestra dinamica: aumentare la soglia se count giornaliero supera X.
- Logging breakdown (#excluded, #included).


### ROI Timeline API (Iterazione 27)

Endpoint: GET /roi/timeline  
Parametri:
- limit (int, default 200, max 2000) → record timeline (ordinati per ts, restituiti gli ultimi).
- start_date / end_date (YYYY-MM-DD) → filtro inclusivo su data (derivata da ts).
- mode = full | daily | both → controlla cosa includere in risposta.
  * full  → solo timeline
  * daily → solo aggregazione giornaliera
  * both  → entrambi (default)

Risposta:
{
  "enabled": true,
  "mode": "both",
  "count": <num timeline items>,
  "items": [ {ts, total_picks, settled_picks, profit_units, yield, hit_rate}, ... ],
  "daily": {
     "2025-10-01": { last_ts, runs, total_picks, settled_picks, profit_units, yield, hit_rate },
     ...
  },
  "filters": {...},
  "included": {"timeline": true/false, "daily": true/false}
}

Origine dati:
- roi_history.jsonl (append ad ogni run) → timeline
- roi_daily.json (aggiornato ad ogni run) → aggregato giornaliero

Note implementative:
- Nessuna nuova variabile env.
- Se tracking o timeline disabilitati: enabled=false, output vuoto coerente.
- Filtro date applicato sia a timeline che daily.
- limit applicato dopo filtraggio.

Evoluzioni possibili:
- Paginazione (cursor o offset).
- Rolling metrics (7d/30d) lato API.
- Endpoint /roi/timeline/metrics con derivazioni (max drawdown, profit curve).

### Kelly Staking (Iterazione 28)

Scopo:
Adattare lo stake di ogni pick ROI alla probabilità stimata (modello o consensus) e alle quote, usando una versione semplificata del Kelly Criterion.

Formula (bet singolo):
fraction = (decimal_odds * p - 1) / (decimal_odds - 1)
dove p è la probabilità modello (prediction) o blended (consensus).  
Se fraction <= 0 → fallback a stake fisso (roi_stake_units).  
Se fraction > 0:
  fraction_capped = min(fraction, KELLY_EDGE_CAP)
  stake = min(fraction_capped * KELLY_BASE_UNITS, KELLY_MAX_UNITS)

Config:
- ENABLE_KELLY_STAKING (default false)
- KELLY_BASE_UNITS (default 1.0)
- KELLY_MAX_UNITS (default 3.0)
- KELLY_EDGE_CAP (default 0.5)

Ledger campi aggiunti:
- stake_strategy: "kelly" | "fixed"
- kelly_fraction: frazione teorica (non cap) o null
- kelly_fraction_capped: frazione dopo cap
- kelly_prob: probabilità usata (p) o null
- kelly_b: (decimal_odds - 1)

Note:
- Per consensus picks si usa consensus.blended_prob[side].
- Se prob mancante o invalida (fuori 0..1): fallback fisso.
- ROI metrics rimangono coerenti; profit e yield già calcolati su stake effettivo.

Evoluzioni future:
- Kelly frazionata con scaling tempo (dopo n picks).
- Multi outcome book adjustment (ridurre p in presenza di overround elevato).
- Esclusione pick negative (skip invece di fallback).


### ROI Source Breakdown (Iterazione 29)

Aggiunte metriche aggregate per distinguere performance tra sorgenti:
Campi aggiunti in roi_metrics.json:
- picks_prediction / picks_consensus
- settled_prediction / settled_consensus
- open_prediction / open_consensus
- wins_prediction / wins_consensus
- losses_prediction / losses_consensus
- profit_units_prediction / profit_units_consensus
- yield_prediction / yield_consensus
- hit_rate_prediction / hit_rate_consensus

Metodo:
1. Raggruppo ledger per source.
2. Riutilizzo funzione interna di calcolo profit/stats.
3. Integro i risultati nel payload finale di metrics.

Motivazione:
- Consente analisi strategica (fonte che genera edge reale).
- Nessuna modifica all’endpoint /roi (metrics già pass-through).
- Backward-compat: i campi originali invariati.

Evoluzioni possibili:
- Breakdown anche per value_type (prediction_value vs consensus_value).
- Breakdown per mese (rolling counters).
- Aggiunta variabili per escludere una source in ROI (già parziale via ROI_INCLUDE_CONSENSUS).
