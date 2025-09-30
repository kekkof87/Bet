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

## Data Contracts
- FixtureRecord (dataclass normalizzata: fixture_id, league_id, season, date_utc, home_team, away_team, status, home_score, away_score, provider)
- Delta Output (detailed):
  - added: List[FixtureRecord]
  - removed: List[FixtureRecord]
  - modified: List[{old: FixtureRecord, new: FixtureRecord, change_type: str}]
  - change_breakdown: Dict[str,int] (score_change, status_change, both, other)

## Quality & CI
- Lint: Ruff
- Typecheck: mypy
- Test: Pytest
- Coverage (planned / workflow draft)
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
3. Se configurato `FETCH_ABORT_ON_EMPTY=1` e `new` è vuoto → abort senza salvare
4. Calcola diff/classification: `detailed = diff_fixtures_detailed(old, new, ...)`
5. Se `old` non vuoto → salva previous (`fixtures_previous.json`)
6. Salva latest (`fixtures_latest.json`)
7. (Se `ENABLE_HISTORY=1`) salva snapshot timestamped + rotazione
8. Log JSON strutturato con summary e breakdown

### Persistenza
| File | Scopo | Trigger |
|------|-------|---------|
| fixtures_latest.json | Stato corrente canonicale | Ogni fetch riuscito |
| fixtures_previous.json | Stato precedente immediato | Solo se esisteva un vecchio stato |
| history/fixtures_YYYYmmdd_HHMMSS.json | Snapshot storico (opzionale) | Se ENABLE_HISTORY=1 |

### Algoritmo Diff (Sintesi)
- Indicizzazione per chiave primaria preferenziale: `fixture_id`
- Fallback chiave composita: `(league_id, date_utc, home_team, away_team)` (record incompleti scartati)
- added: chiavi nuove
- removed: chiavi mancanti
- modified: coppie con differenze (limitato da compare_keys se impostato)
- classification: determinata confrontando punteggio e status

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
- `HISTORY_MAX` (default 30) → rotazione automatica (mantiene gli snapshot più recenti)

Motivazioni:
- Audit evolutivo
- Possibile replay/analisi retrospettiva

### Fetch Stats (Telemetria Iniziale)
Campo `fetch_stats` nel log (placeholder attuale, verrà unificato quando il provider userà un unico client con retry).
Struttura:
```
{
  "attempts": <int>,
  "retries": <int>,
  "latency_ms": <float>,
  "last_status": <int | null>
}
```

## Error Handling (Principali)
| Scenario | Comportamento |
|----------|---------------|
| API key assente | Abort con messaggio |
| Errore I/O salvataggio previous | Log errore, continua |
| Errore I/O salvataggio latest | Log errore (stato non avanza) |
| Snapshot corrotto | Warning, trattato come [] |
| Diff exception interna | Catturata, logged, delta vuoto |
| Fetch vuoto + abort_on_empty | Non salva né previous né latest |

## Retrocompatibilità
- `LATEST_FIXTURES_FILE` statico ancora presente per test.
- Doppio provider legacy in fase di consolidamento (in corso).

## Estensioni Future (Prioritized)
| Idea | Descrizione | Priorità |
|------|-------------|----------|
| Unify HTTP client | Un solo client httpx + retry + stats reali | Alta |
| Metrics persistenti | Esportare scoreboard JSON o endpoint | Media |
| Prometheus / OTEL | Esposizione metrics & tracing | Media |
| Event streaming | Pubblicare delta come eventi incrementali | Bassa |
| Advanced filtering | Trigger su soli score_change | Media |
| Model validation ISO | Validare date_utc formato ISO | Media |
| Snapshot diff storage | Conservare differenze classifiche / ranking | Bassa |

## Complessità
- Diff O(n) (indicizzazione + set operations).
- Memory: due mappe indicizzate + struttura modifiche.

## Rischi Mitigati
| Rischio | Mitigazione |
|---------|-------------|
| Corruzione file | Scrittura atomica |
| Crescita illimitata snapshot | Rotazione HISTORY_MAX |
| Rumore modifiche non rilevanti | compare_keys / classification |
| Perdita stato per fetch vuoto | FETCH_ABORT_ON_EMPTY |

## Integrazione Futura
- Telegram parsing sfrutterà classification per correlare messaggi a score_change.
- AI reasoning potrà eseguire solo su subset modificato.
- Dashboard potrà mostrare breakdown cambi giornalieri.

## Sintesi
Il layer Delta + Classification + History fornisce un’infrastruttura incrementale pronta per evolvere verso analisi avanzate e automazioni senza introdurre complessità eccessiva.

### Unified Provider & Fetch Stats (Update)
Il provider delle fixtures ora utilizza un unico client con retry/backoff (requests) e produce telemetria reale:
- attempts / retries / latency_ms / last_status
La normalizzazione è centralizzata in `core/normalization.py`.
Il vecchio client httpx è deprecato (vedi `providers/api_football/client.py`) e verrà rimosso in futuro.

### Metrics & Events (Nuovo)
Se `ENABLE_METRICS_FILE=true` viene scritto `metrics/last_run.json` (dentro `BET_DATA_DIR`) con:
```json
{
  "summary": {...},
  "change_breakdown": {...},
  "fetch_stats": {...},
  "total_fixtures": N
}
```
Se `ENABLE_EVENTS_FILE=true` e il delta non è vuoto viene scritto `events/last_delta.json` con i dettagli (added/removed/modified + breakdown).

Variabili:
- ENABLE_METRICS_FILE (default true)
- ENABLE_EVENTS_FILE (default true)
- METRICS_DIR (default metrics)
- EVENTS_DIR (default events)

### Validazione date_utc
La normalizzazione aggiunge `valid_date_utc` basato su regex ISO 8601 semplice. In caso di mismatch viene loggato un warning solo alla prima occorrenza.
