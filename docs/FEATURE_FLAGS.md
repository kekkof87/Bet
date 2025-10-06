# FEATURE FLAGS & CONFIG REFERENCE

Questo documento elenca tutte le variabili di ambiente (repository “Actions Variables” o `.env`) che controllano il comportamento dell’applicazione, in particolare il motore ROI / Regime e le analitiche avanzate.  
Tutte le variabili non obbligatorie hanno valori di default “safe” (disattivi) e possono essere abilitate progressivamente per i test.

---

## 1. Struttura del Sistema (Riassunto)

| Macro Area | Scopo | File Principali |
|------------|-------|-----------------|
| Ingestion / Fixtures | Recupero e salvataggio eventi sportivi | `providers/api_football/*`, `core/persistence.py` |
| Predictions / Consensus | Generazione probabilità e blending | `predictions/*`, `consensus/*` |
| Value Detection & Alerts | Individuazione pick con edge | `predictions/value.py`, `predictions/value_alerts.py` |
| ROI Engine | Ledger pick, settlement, metriche estese | `analytics/roi.py` |
| Regime Engine (M1) | Classificazione stato strategia (bull/bear/volatile/...) | `analytics/roi.py` (sezione regime) |
| API / Backend | Endpoint REST | `api/app.py`, `api/routes/*` |
| Export & Monitoring | CSV, schema, Prometheus (stub), compact export | `analytics/roi.py`, `monitoring/prometheus_exporter.py` |

---

## 2. Variabili Obbligatorie Minime

| Variabile | Descrizione | Note |
|-----------|-------------|------|
| `API_FOOTBALL_KEY` | Chiave provider dati principali | NECESSARIA per ingestion reali |
| `BET_DATA_DIR` | Directory radice dati | Default: `data` |

Per un primo avvio “offline” puoi usare una chiave dummy ma le chiamate reali falliranno.

---

## 3. ROI Core & Regime

| Variabile | Default | Tipo | Descrizione |
|-----------|---------|------|-------------|
| `ENABLE_ROI_TRACKING` | 0 | bool | Attiva il motore ROI (ledger + metriche) |
| `ROI_DIR` | roi | str | Sottocartella dentro `BET_DATA_DIR` |
| `ROI_MIN_EDGE` | 0.05 | float | Soglia edge minima per includere una pick |
| `ROI_STAKE_UNITS` | 1.0 | float | Stake fisso base (se Kelly off) |
| `ENABLE_ROI_TIMELINE` | 1 | bool | Salva timeline equity (jsonl) + daily snapshot |
| `ROI_TIMELINE_FILE` | roi_history.jsonl | str | Nome file timeline |
| `ROI_DAILY_FILE` | roi_daily.json | str | File snapshot giornaliero |

### Regime (Stub vs M1)

| Variabile | Default | Possibili | Effetto |
|-----------|---------|-----------|---------|
| `ENABLE_ROI_REGIME` | 0 | 0/1 | Attiva modulo regime |
| `ROI_REGIME_VERSION` | stub | stub/m1 | M1 abilita classificazione avanzata + metrics_version 3.0 |
| `ROI_REGIME_LOOKBACK` | 150 | int | Punti equity considerati (max) |
| `ROI_REGIME_MIN_POINTS` | 30 | int | Min punti per classificazione M1 (riduci in test: es. 10) |
| `ROI_REGIME_MIN_HOLD` | 8 | int | Protezione flip (run minimi prima di cambio stato) |
| `ROI_REGIME_SMOOTH_ALPHA` | 0.4 | float (0–1) | SMA esponenziale momentum |
| `ROI_REGIME_MOM_THRESHOLD` | 0.002 | float | Soglia momentum neutro vs bull/bear/correction |
| `ROI_REGIME_MOMENTUM_WINDOWS` | 10,30 | lista int | Finestre increments per feature |
| `ROI_REGIME_DD_BEAR` | 0.25 | float | Drawdown % per bear |
| `ROI_REGIME_VOL_HIGH` | 0.20 | float | Soglia vol per regime volatile |
| `ENABLE_ROI_REGIME_PERSISTENCE` | 0 | bool | Salva stato regime su file |
| `ROI_REGIME_STATE_FILE` | roi_regime_state.json | str | Nome file stato |
| `ROI_REGIME_HISTORY_MAX` | 30 | int | Transizioni massime conservate |

---

## 4. Staking & Kelly

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `ENABLE_KELLY_STAKING` | 0 | Calcola stake dinamico |
| `KELLY_BASE_UNITS` | 1.0 | Base capital per frazione Kelly |
| `KELLY_MAX_UNITS` | 3.0 | Tetto stake |
| `KELLY_EDGE_CAP` | 0.5 | Cap frazione Kelly (protezione outlier) |
| `ENABLE_ROI_KELLY_EFFECT` | 0 | Blocchi metriche uplift vs fisso |

---

## 5. Edge, CLV & Buckets

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `ENABLE_CLV_CAPTURE` | 1 | Calcola CLV (closing odds) |
| `CLV_ODDS_SOURCE` | odds_latest | Sorgente closing |
| `ENABLE_ROI_CLV_AGGREGATE` | 1 | Statistiche aggregazione CLV |
| `ENABLE_ROI_EDGE_DECILES` | 1 | Dividi picks in decili d’edge |
| `ROI_EDGE_BUCKETS` | 0.05-0.07,0.07-0.09,... | Range personalizzati edge |
| `ENABLE_ROI_CLV_BUCKETS` | 0 | Attiva bucket CLV |
| `ROI_CLV_BUCKETS` | -0.1--0.05,-0.05-0,... | Formato generico `<L>-<R>` (vuoto = open ended) |
| `ENABLE_ROI_PROFIT_BUCKETS` | 0 | Bucket per profit contribution |
| `ROI_PROFIT_BUCKETS` | -2--1,-1--0.5,... | Range profitti per pick |

---

## 6. Distribuzioni & Montecarlo

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `ENABLE_ROI_PROFIT_DISTRIBUTION` | 1 | Quartili / skew profit per pick |
| `ENABLE_ROI_PAYOUT_MOMENTS` | 0 | Skewness & kurtosis |
| `ENABLE_ROI_MONTECARLO` | 0 | Simulazione equity bootstrap |
| `ROI_MC_RUNS` | 150 | Numero simulazioni (riduci per test) |
| `ROI_MC_WINDOW` | 200 | Ampiezza finestra incrementi |

---

## 7. Rischio & Volatilità

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `ENABLE_ROI_RISK_METRICS` | 1 | Sharpe-like, Sortino-like, stddev |
| `ENABLE_ROI_EQUITY_VOL` | 1 | Vol incrementi equity |
| `ROI_EQUITY_VOL_WINDOWS` | 30,100 | Finestre vol |
| `ENABLE_ROI_ANOMALY_FLAGS` | 1 | Flag drawdown / yield drop / vol spike |
| `ROI_ANOMALY_DD_THRESHOLD` | 0.30 | Soglia dd alert |
| `ROI_ANOMALY_YIELD_DROP` | 0.50 | Δ yield totale vs rolling |
| `ROI_ANOMALY_VOL_MULT` | 2.0 | Rapporto vol “spike” |
| `ENABLE_ROI_ROR` | 0 | Stima risk-of-ruin |

---

## 8. Breakdown & Segmentazione

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `ENABLE_ROI_SOURCE_BREAKDOWN` | 1 | Statistiche per source |
| `ENABLE_ROI_STAKE_BREAKDOWN` | 1 | Fisso vs kelly |
| `ENABLE_ROI_LEAGUE_BREAKDOWN` | 0 | Statistiche per lega |
| `ROI_LEAGUE_MAX` | 10 | Limite leghe |
| `ENABLE_ROI_TIME_BUCKETS` | 0 | Finestra oraria picks |
| `ENABLE_ROI_SIDE_BREAKDOWN` | 1 | Home/Draw/Away |
| `ENABLE_ROI_AGING_BUCKETS` | 0 | Bucket tempo settlement |
| `ROI_AGING_BUCKETS` | 1,2,3,5,7 | Giorni cumulativi |

---

## 9. Performance & Correlazioni

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `ENABLE_ROI_SOURCE_EFFICIENCY` | 1 | Efficienza profit/std per source |
| `ENABLE_ROI_EDGE_CLV_CORR` | 0 | Correlazione edge–CLV |
| `ENABLE_ROI_STAKE_ADVISORY` | 0 | Consigli riduzione stake in drawdown |
| `ROI_STAKE_ADVISORY_DD_PCT` | 0.25 | Soglia drawdown relativo |

---

## 10. Rate Limit & Selezione

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `ROI_MAX_NEW_PICKS_PER_DAY` | 0 | 0 = no limit |
| `ROI_RATE_LIMIT_STRICT` | 1 | Se superato limita ingressi |
| `MERGED_DEDUP_ENABLE` | 0 | Rimuove duplicati prediction/consensus se esiste merged |
| `ROI_INCLUDE_CONSENSUS` | 1 | Include picks consensus |
| `ROI_INCLUDE_MERGED` | 1 | Include picks merged |
| `VALUE_ALERT_DYNAMIC_ENABLE` | 0 | Tuning dinamico soglia value |
| `VALUE_ALERT_DYNAMIC_TARGET_COUNT` | 50 | Target picks periodo |
| `VALUE_ALERT_DYNAMIC_MIN_FACTOR` | 1.0 | Min moltiplicatore soglia |
| `VALUE_ALERT_DYNAMIC_MAX_FACTOR` | 2.0 | Max moltiplicatore |
| `VALUE_ALERT_DYNAMIC_ADJUST_STEP` | 0.05 | Incremento aggiustamento |

---

## 11. Pruning & Archivio

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `ROI_LEDGER_MAX_AGE_DAYS` | 0 | Età massima (0 = infinito) |
| `ROI_LEDGER_MAX_PICKS` | 0 | Contatore massimo (0 = infinito) |
| `ENABLE_ROI_LEDGER_ARCHIVE` | 1 | Abilita spostamento in `ledger_archive.json` |
| `ENABLE_ROI_ARCHIVE_STATS` | 0 | Calcolo block `archive_stats` |

---

## 12. Export & Output

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `ENABLE_ROI_CSV_EXPORT` | 1 | Genera CSV ledger |
| `ROI_CSV_FILE` | roi_export.csv | Nome file |
| `ROI_CSV_INCLUDE_OPEN` | 1 | Include picks aperte |
| `ROI_CSV_SORT` | created_at | created_at / settled_at |
| `ROI_CSV_LIMIT` | 0 | 0 = illimitato |
| `ENABLE_ROI_COMPACT_EXPORT` | 0 | ROI compatto |
| `ENABLE_ROI_SCHEMA_EXPORT` | 0 | Esporta schema chiavi |
| `ENABLE_ROI_ODDS_SNAPSHOT` | 1 | Allegare snapshot mercato |
| `ENABLE_ROI_PAYOUT_MOMENTS` | 0 | Aggiunge statistica extra payout |
| `ENABLE_PROMETHEUS_EXPORTER` | 0 | Export metriche (stub / da implementare) |

---

## 13. Variabili Alerts / Value

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `ENABLE_VALUE_DETECTION` | 0 | Pipeline value detection |
| `VALUE_MIN_EDGE` | 0.05 | Edge minimo generico |
| `ENABLE_VALUE_ALERTS` | 0 | Scrive value_alerts.json |
| `VALUE_ALERT_MIN_EDGE` | (VALUE_MIN_EDGE) | Soglia dedicata alerts |
| `VALUE_ALERTS_DIR` | value_alerts | Cartella |
| `ENABLE_VALUE_HISTORY` | 0 | Archivia snapshot value |
| `VALUE_HISTORY_MODE` | daily | daily/rolling |
| `VALUE_HISTORY_MAX_FILES` | 30 | Rotazione file |

---

## 14. Previsioni / Consensus

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `ENABLE_PREDICTIONS` | 0 | Attiva salvataggio predictions |
| `ENABLE_PREDICTIONS_USE_ODDS` | 0 | Usa odds in features |
| `MODEL_BASELINE_VERSION` | baseline-v1 | Identificatore modello |
| `ENABLE_CONSENSUS` | 0 | Attiva blended consensus |
| `CONSENSUS_BASELINE_WEIGHT` | 0.6 | Peso baseline vs altro |

---

## 15. Esempio Setup “Baseline + Regime M1”

```bash
API_FOOTBALL_KEY=CHiAVE_REALE
BET_DATA_DIR=data
ENABLE_ROI_TRACKING=1
ENABLE_ROI_REGIME=1
ROI_REGIME_VERSION=m1
ENABLE_ROI_REGIME_PERSISTENCE=1
ROI_REGIME_MIN_POINTS=10
ENABLE_KELLY_STAKING=1
ENABLE_ROI_KELLY_EFFECT=1
ENABLE_ROI_PROFIT_DISTRIBUTION=1
```

---

## 16. Scenario di Test Progressivo

| Step | Abilita | Cosa Verificare |
|------|---------|-----------------|
| 1 | ENABLE_ROI_TRACKING=1 | Creazione `roi_metrics.json` |
| 2 | Kelly | Campi `kelly_*` nelle pick |
| 3 | CLV Capture | `clv_pct` nei picks settled |
| 4 | Edge Deciles | `edge_deciles` non vuoto |
| 5 | Montecarlo | Blocco `montecarlo` |
| 6 | Regime Stub | `regime.label` (version=stub) |
| 7 | Regime M1 | `metrics_version=3.0` + momentum_smooth |
| 8 | Archive Stats + Pruning | `archive_stats` popolato |
| 9 | Profit Buckets + Payout Moments | Blocchi `profit_buckets`, `payout_moments` |
| 10 | Compact & Schema Export | File `roi_metrics_compact.json`, `roi_metrics.schema.json` |

---

## 17. Reset Rapido (Baseline Pulita)

Impostare (o rimuovere) per tornare a comportamento base:

```bash
ENABLE_ROI_REGIME=0
ENABLE_ROI_KELLY_EFFECT=0
ENABLE_ROI_MONTECARLO=0
ENABLE_ROI_PROFIT_BUCKETS=0
ENABLE_ROI_PAYOUT_MOMENTS=0
ENABLE_ROI_CLV_BUCKETS=0
ENABLE_ROI_AGING_BUCKETS=0
ENABLE_ROI_COMPACT_EXPORT=0
ENABLE_ROI_SCHEMA_EXPORT=0
ROI_LEDGER_MAX_AGE_DAYS=0
ROI_LEDGER_MAX_PICKS=0
```

---

## 18. Troubleshooting Rapido

| Sintomo | Possibile Causa | Azione |
|---------|-----------------|--------|
| `ValueError: API_FOOTBALL_KEY` | Mancanza chiave | Imposta variable in repository |
| `metrics_version` resta 2.0 | Regime M1 non attivo | Verifica `ENABLE_ROI_REGIME=1` e `ROI_REGIME_VERSION=m1` |
| Nessun `clv_pct` | Odds closing mancanti | Controlla `odds_latest.json` + `ENABLE_CLV_CAPTURE=1` |
| `montecarlo` vuoto | Pochi settled picks | Aumenta numero pick o riduci `ROI_MC_WINDOW` |
| `edge_clv_corr.n` piccolo | < 10 pick con edge & CLV | Accumula più partite |

---

## 19. Note di Sicurezza

- Non esporre pubblicamente `API_FOOTBALL_KEY`.
- Per test rapidi, usa flag *minimali* per ridurre rumore (es. lascia Montecarlo disattivo se non lo stai valutando).
- M1 Regime produce file stato persistente: se desideri test pulito, elimina `roi_regime_state.json`.

---

## 20. Futuri Step (Roadmap Sintetica)

| Fase | Obiettivo | Dipendenze |
|------|-----------|------------|
| M2 Adaptive Stake | Modulare stake in base a regime + drawdown | M1 stabile |
| M3 Adaptive Edge | Soglia ROI_MIN_EDGE dinamica | M2 |
| M4 Drift Monitor | Segnalare degrado edge vs CLV | CLV affidabile |
| M5 Stress Scenarios | Simulare serie negative | Montecarlo validato |
| M6 Portfolio Layer | Multi-strategy / pesi dinamici | Source efficiency |

---

**Versione Documento:** 1.0  
**Ultimo Aggiornamento:** (aggiorna manualmente al prossimo cambio)

Se ti serve una versione in inglese o un matrix workflow di CI automatico per i flag, apri una issue dedicata.

---
