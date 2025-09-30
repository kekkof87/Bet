# Architecture Overview

## Flow (Current Scope)
1. Fetch fixtures (scheduled GitHub Action)
2. Validate & persist (atomic write)
3. Delta computation (added / removed / modified) + snapshot previous
4. (Planned) Telegram parsing
5. (Planned) AI reasoning & prediction synthesis
6. (Planned) Consensus & scoring
7. (Planned) Frontend consumption & dashboards
8. (Planned) Post-match analytics

## Modules Roadmap
- core/: configuration, logging, persistence, diff (delta logic), models
- providers/: API adapters (API-Football attuale, altri futuri)
- telegram/: parsing & normalization (planned)
- ai/: feature engineering & reasoning (planned)
- consensus/: merging signals (planned)
- web/ or frontend/: UI delivery (planned)

## Data Contracts
- FixtureRecord (vedi models.py)
- Delta Output (in-memory, non ancora formalizzato come modello):
  - added: List[FixtureRecord]
  - removed: List[FixtureRecord]
  - modified: List[Tuple[FixtureRecord_old, FixtureRecord_new]]

## Quality & CI
- Lint: Ruff
- Typecheck: mypy (approccio incrementale, strict graduale)
- Test: Pytest (+ future coverage badge)
- Scheduled data fetch (GitHub Actions)
- Delta logging strutturato per osservabilità

## Delta Fixtures (Nuova Sezione)

### Obiettivi
Garantire:
- Tracciabilità delle variazioni tra ultimo snapshot e nuovo insieme di fixtures.
- Persistenza dello snapshot precedente per audit / debug.
- Riepilogo numerico (added, removed, modified, total_new) nei log JSON.

### File Coinvolti
- Nuovo: `src/core/diff.py`
- Modifica: `scripts/fetch_fixtures.py`
- Modifica: `src/core/persistence.py` (aggiunta `save_previous_fixtures`)
- Test: `tests/test_fixtures_diff.py`

### Flusso Delta (dettaglio)
1. Carica stato precedente: `old = load_latest_fixtures()`
2. Fetch nuove fixtures dal provider (API-Football) → `new`
3. Calcola delta: `added, removed, modified = diff_fixtures(old, new)`
4. Se `old` non vuoto → salva snapshot previous (`fixtures_previous.json`)
5. Salva nuovo snapshot latest (`fixtures_latest.json`)
6. Logga riepilogo: `{"added": X, "removed": Y, "modified": Z, "total_new": N}`

### Persistenza
| File | Scopo | Trigger |
|------|-------|---------|
| fixtures_latest.json | Stato corrente canonicale | Ogni fetch riuscito |
| fixtures_previous.json | Stato precedente immediato | Solo se esisteva un vecchio stato |
| (Legacy) data/fixtures_latest.json | Retrocompatibilità test / path statico | Duplicato condizionale |

### Algoritmo Diff
Implementato in `core.diff`:
- Indicizzazione per chiave primaria preferenziale: `fixture_id`
- Fallback chiave composita: `(league_id, date_utc, home_team, away_team)`
- Confronto:
  - added = chiavi nuove
  - removed = chiavi mancanti
  - modified = chiavi in comune con differenze (confronto shallow su dict, opz. subset chiavi future)
- Funzione helper `summarize_delta(...)` per logging.

### Logging
Esempio linea (JSON):
```
{"ts":"2025-01-01T10:00:00Z","level":"INFO","logger":"scripts.fetch_fixtures","msg":"fixtures_delta {'added': 2, 'removed': 1, 'modified': 3, 'total_new': 120}"}
```
Futuro miglioramento: log come oggetto (non string dict) usando `extra` oppure serializzazione dedicata.

### Error Handling
| Scenario | Comportamento |
|----------|---------------|
| API key assente | Abort con messaggio chiaro |
| Errore I/O salvataggio previous | Log error, continua (best effort) |
| Errore I/O salvataggio latest | Log error (lo stato non avanza) |
| JSON corrotto snapshot precedente | Ignorato, log warning, procede come se old = [] |
| Diff exception interna (teorica) | Da gestire in futuro con try/except wrapper se necessario |

### Retrocompatibilità
- Manteniamo ancora la costante `LATEST_FIXTURES_FILE` per test esistenti.
- Nessun breaking change per gli script esterni: l’interfaccia di fetch (provider) invariata.

### Estensioni Future
| Idea | Descrizione | Priorità |
|------|-------------|----------|
| Filtri compare_keys | Limitare modified a campi es: punteggi, status | Media |
| Storage storico versionato | Archiviazione con timestamp (es: fixtures_2025-01-01T10-00.json) | Alta |
| Metriche Prometheus | Esposizione counters delta | Media |
| Event streaming | Pubblicare delta su coda (Kafka / Redis Streams) | Bassa |
| Deduplicate unchanged log | Skippare log se delta vuoto | Bassa |
| Normalizzazione hash | Hash deterministico record per diff profondo | Media |

### Complessità
- Diff O(n) medio (due pass per indicizzazione + confronto) con n = max(len(old), len(new)).
- Memory: due dict indicizzati → accettabile per volumi tipici di fixtures giornaliere.

### Rischi Mitigati
| Rischio | Mitigazione |
|---------|-------------|
| Corruzione latest | Scrittura atomica + fsync + rename |
| Race run concorrenti | Azione GitHub schedulata → single writer (accettato) |
| Cambi schema fixture | Diff grace (fallback composite key) |
| Crescita file previous | Sovrascrive, non accumula (richiede storico separato se serve) |

## Futuri Passi Chiave
1. Aggiungere retention storica / archivio versionato.
2. Documentare FixtureRecord formalmente (pydantic dataclass futura).
3. Introdurre compare_keys configurabile (env / CLI).
4. Aggiungere test e2e fetch + delta (integrazione).
5. Esportare metrics (Prometheus / OpenTelemetry).
6. Logging delta come structured object (non stringa del dict).

## Integrazione con Fasi Future
- Telegram parsing potrà usare il delta per correlare eventi messaggio ↔ cambi stato fixture.
- AI reasoning può reagire solo a modified (riducendo compute).
- Consensus/Scoring può ricalcolare partizioni solo su subset changed.

## Sintesi
Il layer Delta aggiunge osservabilità e tracciabilità tra snapshot consecutivi con impatto minimo sul resto dell’architettura, preparando il terreno per storicizzazione e processamento incrementale.
