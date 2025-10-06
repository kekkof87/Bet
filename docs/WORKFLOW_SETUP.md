# Workflow ROI Cycle – Setup

## Obiettivo
Eseguire automaticamente (cron o manuale) il ciclo:
1. Fetch fixtures (giorno corrente)
2. Predictions
3. Value detection & alerts (già integrate nel pipeline)
4. ROI build/update (ledger, metrics, regime, export)
5. Caricamento artifacts (metrics, csv, compact, timeline)

## Variabili Necessarie

| Tipo | Nome | Note |
|------|------|------|
| Secret | API_FOOTBALL_KEY | Chiave provider |
| Variable | ENABLE_PREDICTIONS | 1 |
| Variable | ENABLE_VALUE_ALERTS | 1 |
| Variable | ENABLE_VALUE_DETECTION | 1 |
| Variable | ENABLE_ROI_TRACKING | 1 |
| Variable | ENABLE_ROI_REGIME | 1 |
| Variable | ROI_REGIME_VERSION | m1 |
| Variable | ENABLE_ROI_REGIME_PERSISTENCE | 1 |
| Variable | ROI_REGIME_MIN_POINTS | 10 |
| Variable | ROI_LEDGER_MAX_AGE_DAYS | 45 |
| Variable | ENABLE_ROI_ARCHIVE_STATS | 1 |
| Variable | ENABLE_ROI_COMPACT_EXPORT | 1 |
| Variable | ENABLE_ROI_SCHEMA_EXPORT | 1 |
| Variable | ENABLE_KELLY_STAKING | 1 |
| Variable | KELLY_BASE_UNITS | 1.0 |
| Variable | KELLY_MAX_UNITS | 3.0 |
| Variable | KELLY_EDGE_CAP | 0.5 |
| Variable | ENABLE_ROI_KELLY_EFFECT | 1 |
| Variable | ENABLE_ROI_MONTECARLO | 1 |
| Variable | ROI_MC_RUNS | 50 |
| Variable | ROI_MC_WINDOW | 150 |
| Variable | ENABLE_ROI_PROFIT_BUCKETS | 1 |
| Variable | ROI_PROFIT_BUCKETS | -2--1,-1--0.5,-0.5-0,0-0.5,0.5-1,1- |
| Variable | ENABLE_ROI_CLV_BUCKETS | 1 |
| Variable | ROI_CLV_BUCKETS | -0.05-0,0-0.05,0.05-0.1,0.1- |

## File Aggiunti
- `.github/workflows/roi_cycle.yml`
- `scripts/run_cycle.py`
- `scripts/run_single_settlement_demo.py` (opzionale)
- `docs/WORKFLOW_SETUP.md`

## Esecuzione Manuale
Da tab *Actions* → `ROI Scheduled Cycle` → `Run workflow`.

Parametri:
- `force_settlement_demo=true` (facoltativo) per simulare un settlement artificiale durante test.

## Output Atteso
Dopo il job:
- Artifacts:
  - `roi_metrics.json`
  - `roi_metrics_compact.json` (se flag)
  - `roi_export.csv`
  - `roi_history.jsonl`
  - `roi_daily.json`
  - `roi_regime_state.json` (se persistence ON)

## Troubleshooting
| Problema | Possibile Causa | Soluzione |
|----------|-----------------|-----------|
| `API_FOOTBALL_KEY` errore | Secret mancante | Aggiungi secret |
| Nessun pick | value_alerts non generate | Verifica dataset / edge / soglie |
| `regime` neutrale sempre | Non abbastanza punti / MIN_POINTS troppo alto | Riduci ROI_REGIME_MIN_POINTS (es. 10) |
| Montecarlo vuoto | Poche pick settled | Attendere settlement reale / simulare con script demo |

## Modifiche Cron
File: `.github/workflows/roi_cycle.yml`  
Linea:
```
schedule:
  - cron: "15 * * * *"
```
Ad es. ogni 30 minuti: `"*/30 * * * *"` (attenzione al rate limit provider).

## Best Practice
- Mantenere ROI_MC_RUNS moderato (30–50) nei test.
- Non abilitare tutte le feature se non servono (performance).
- Ruotare i dati vecchi: ROI_LEDGER_MAX_AGE_DAYS=45 (o 60).

---
