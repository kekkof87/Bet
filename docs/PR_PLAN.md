# Betting Dashboard — Piano di Realizzazione e PR unica

Stato attuale (assunto)
- Backend FastAPI presente (backend/api/main.py) con health e pochi endpoint base.
- GUI Streamlit (frontend/gui/streamlit_app.py) in esecuzione con pagine minime.
- Script attivi:
  - fetch_fixtures_football_data.py (fixtures reali)
  - fetch_results_football_data.py (storico risultati) — DA AGGIUNGERE in questa PR
  - predict_elo_fdo.py (predizioni basate su Elo) — DA AGGIUNGERE
- Dati salvati in data/fixtures.json, data/last_delta.json, data/history/results.jsonl, data/latest_predictions.json.
- VS Code tasks.json già evoluto.

Obiettivi funzionali richiesti
1) Eventi
   - Lista partite con quote, filtrabile per:
     - Oggi
     - Prossimi 2 giorni
     - Prossimi 7 giorni
   - Raggruppamento per campionato/lega
   - Visione rapida “miglior quota” (best book) per mercato 1X2 (+ espandibile ad altri mercati successivamente)

2) Settings
   - Gestione chiavi/API dal front-end (salvataggio in .env senza toccare file a mano)
   - Parametri pipeline (finestra fetch, soglie value-picks, soglie ROI)
   - Test connessione provider (ping / status)
   - Selezione tema (chiaro/scuro) e layout UI

3) Telegram channel
   - Lista canali, aggiunta/rimozione
   - Ingest dei messaggi (pulsante “Sincronizza ora”)
   - Parsing picks con normalizzazione (team+mercato+quota)
   - Vista per singolo tipster con storico consigli e relativo esito (win/loss/pending)
   - NOTA: serve definire un primo set di canali (vedi più sotto)

4) Classifica Tipster
   - Classifica basata su metriche:
     - Hit rate (win%)
     - ROI/Yield (se abbiamo puntata e quota)
     - Profit/Loss
     - Volume picks
   - Filtri temporali (7/30/90 giorni, stagione, custom)
   - Esportazione CSV

5) Pronostici
   - Incrocio tra:
     - Modello (Elo FDO iniziale, poi estensibile a più modelli)
     - Quote bookmaker
     - Consenso tipster (opzionale: peso dei tipster “top”)
   - Output:
     - Probabilità 1X2 (e mercati aggiuntivi progressivamente)
     - Fair odds
     - Value picks (edge %), con soglia regolabile
     - Comparazione quote (miglior book vs media)
   - Ordinamento per affidabilità/probabilità attesa

6) Crea Bolletta
   - Input: “quota totale target” (es. 5.00), eventuale numero min/max eventi
   - Algoritmo: selezione suggerita di eventi/pronostici ad alta probabilità per raggiungere la quota desiderata (con approccio greedy iniziale, estendibile a knapsack/ottimizzazione)
   - Output:
     - combinazioni proposte
     - probabilità aggregata di successo stimata
     - quota complessiva e composizione

7) Veste grafica
   - Tema Streamlit personalizzato (.streamlit/config.toml)
   - Layout wide, header semplificati, palette coerente
   - Componenti UI riutilizzabili: cards, tag, indicatori edge/ROI, badge liga

---

Architettura Dati e Provider

- Fixtures/Results: football-data.org (FDO) — già integrato per fixtures, integriamo lo storico risultati.
- Odds (Quote): The Odds API (free tier) come primo provider per 1X2; in futuro potremo aggiungere API-Football Odds o altri provider più completi.
  - Script dedicato: fetch_odds_oddsapi.py
  - Output atteso: data/odds_latest.json con mappatura a eventi (via team names + kickoff).
- Predictions: Elo FDO (già pianificato). In futuro:
  - Modelli multipli e pesatura (consensus).
  - Mercati aggiuntivi (O/U, Doppia Chance).
- Telegram:
  - Ingestion con Telethon (richiede TELEGRAM_API_ID/TELEGRAM_API_HASH).
  - Salvataggio in data/telegram/picks.jsonl + SQLite (data/telegram.db) per velocità query/ROI.
  - Parser normalizza: data evento, lega, teams, mercato, quota, stake (se presente).
  - Resolver risultati: incrocia picks con risultati FDO e marca “win/loss/pending”.

Identificatori e matching eventi
- Chiave primaria “ibrida” per matching cross-provider:
  - date (UTC) arrotondata a 5/15 min
  - normalized home/away (minuscoli, senza punteggiatura, alias)
  - lega opzionale
- Mappa alias squadre (data/aliases/teams.json) per allineare differenze di naming tra provider.
- Fuzzy matching con RapidFuzz come fallback solo per casi incerti (loggati su file).

Struttura file output (principali)
- data/fixtures.json: { items: [ { fixture_id, home, away, league, status, kickoff } ] }
- data/history/results.jsonl: una riga per match concluso con punteggio
- data/latest_predictions.json: { items: [ { fixture_id, home, away, ... probabilities } ] }
- data/odds_latest.json: { items: [ { fixture_key, market, best_odds, books: [...] } ] }
- data/value_picks.json: { items: [ { fixture_id, pick, prob, fair_odds, best_odds, edge, book } ] }
- data/telegram/picks.jsonl e data/telegram.db: picks tipster normalizzati e risolti

---

Backend (FastAPI) — nuovi endpoint

Aggiungeremo router separati in backend/api/routes:
- /events
  - GET /events?range=1|2|7&league=... → fixtures + best odds 1X2
- /predictions
  - GET /predictions?range=... → probabilità modello, fair odds
- /odds
  - GET /odds?fixture_id=... → dettaglio book e quote
- /value-picks
  - GET /value-picks?edge_min=... → lista picks con edge >= soglia
- /tipsters
  - GET /tipsters → elenco tipster + metriche sintetiche
  - GET /tipsters/{id}/picks?range=... → picks del tipster con esiti
  - GET /tipsters/leaderboard?range=... → classifica ROI/hit rate
- /betslip
  - POST /betslip/suggest → input: target_odds, constraints → output: combinazioni consigliate
- /settings
  - GET/POST chiavi e parametri (modifica .env lato server con python-dotenv set_key)
  - GET /status/provider → test connettività

Note:
- Gli endpoint leggeranno i JSON/SQLite sotto data/, non introduciamo DB server-side complessi.
- Validazioni con Pydantic Schema (backend/api/schemas).

---

Frontend (Streamlit) — nuove pagine

1) 01_Eventi.py
   - Header filtri: range (oggi/2/7), per lega, ricerca testuale
   - Tabella per lega: data, home-away, status, best odds 1X2, expander per libri
   - Pulsante “Aggiorna quotes”

2) 02_Pronostici.py
   - Slider soglia edge (es. 3-10%)
   - Tabella value picks con: pick (1/X/2), prob, fair, best odds, edge, book, link all’evento
   - Toggle “includi consenso tipster” (applica bonus/malus probabilità)

3) 03_Crea_Bolletta.py
   - Input: quota target, min/max selezioni, mercati consentiti
   - Output: 1-3 combinazioni consigliate, con probabilità aggregata stimata, quota finale
   - Pulsante “Rigenera” (stocastico leggero) e “Esporta JSON”

4) 04_Telegram_Channel.py
   - Lista canali con on/off + form “Aggiungi canale”
   - Pulsante “Sincronizza ora”
   - Vista per tipster: tab storico picks, filtro per esito, grafico ROI nel tempo
   - “Suggerisci canali” (placeholder: richiede approvazione tua; posso prepopolare se mi autorizzi a fare ricerca)

5) 05_Classifica_Tipster.py
   - Tab classifica: Hit rate, ROI, picks, arco temporale
   - Filtri: periodo, mercato, stake min
   - Download CSV

6) 99_Settings.py
   - Sezione chiavi: FOOTBALL_DATA_API_KEY, ODDS_API_KEY (The Odds API), TELEGRAM_API_ID/HASH, ecc.
   - Parametri pipeline: FETCH_DAYS, soglia edge, timezone, competitions
   - Pulsanti test provider e scrittura .env
   - Selezione tema (tema chiaro/scuro e palette)
   - Pulsanti “Esegui ora”: fetch fixtures, fetch results, fetch odds, predizioni, ricomputo leaderboard

UI/Design
- .streamlit/config.toml con palette light/dark coerente
- CSS aggiuntivo (componenti/cards/tag) in frontend/gui/components/common.py
- Titoli/icone nelle sidebar (Eventi, Pronostici, Bolletta, Tipster, Classifica, Settings)

---

Algoritmi chiave

- Value picks
  - fair_odds = 1 / prob
  - edge = (best_odds - fair_odds) / fair_odds
  - Se edge >= soglia, suggerisci
  - Nota: normalizziamo probabilità del modello (Elo) e, opzionalmente, aggiustiamo con consenso tipster (peso configurabile)

- Crea Bolletta
  - Greedy iniziale: ordina picks per probabilità (o per EV) e seleziona fino a raggiungere target_odds (prodotto quote) rispettando min/max picks.
  - Estensione: knapsack-like con vincoli (massimizzare probabilità aggregata soggetta a quota target).
  - Output: più combinazioni alternative (diversificazione leghe/mercati).

- Tipster
  - Risoluzione outcome: incrocio pick con risultato finale (FDO results).
  - KPI: win%, ROI (se quota e stake note), yield, numero picks, CLV (facoltativo se abbiamo closing line).
  - Leaderboard con filtri.

---

Nuovi script (scripts/)
- fetch_results_football_data.py — storico risultati (FDO)
- predict_elo_fdo.py — modello Elo su fixtures correnti
- fetch_odds_oddsapi.py — quote 1X2 (The Odds API), produce data/odds_latest.json
- telegram_ingest.py — ingest canali via Telethon → data/telegram/picks.jsonl + SQLite
- telegram_resolve_results.py — match picks con risultati → esito

Aggiornamenti VS Code tasks
- Fetch results (FDO - 180 days)
- Predictions: Elo (FDO)
- Fetch odds (OddsAPI)
- Telegram: Ingest now
- Telegram: Resolve results
- Value picks: Generate (backend/cli o script dedicato se preferisci)
- Start API, Start GUI, Open GUI (già presenti)

---

Variabili .env (aggiunte)
- FOOTBALL_DATA_API_KEY=
- ODDS_API_KEY=            # The Odds API
- TELEGRAM_API_ID=
- TELEGRAM_API_HASH=
- TIMEZONE=Europe/Rome
- FETCH_DAYS=7
- LEAGUE_CODES=            # es. PL,SA,PD
- EFFECTIVE_THRESHOLD=0.03 # edge minimo
- DATA_DIR=./data

---

Struttura PR — file da aggiungere/modificare

Aggiunte
- backend/api/routes/events.py
- backend/api/routes/predictions.py
- backend/api/routes/odds.py
- backend/api/routes/value_picks.py
- backend/api/routes/tipsters.py
- backend/api/routes/betslip.py
- backend/api/routes/settings.py
- backend/api/schemas/events.py
- backend/api/schemas/predictions.py
- backend/api/schemas/odds.py
- backend/api/schemas/tipsters.py
- backend/api/schemas/betslip.py
- frontend/gui/pages/01_Eventi.py
- frontend/gui/pages/02_Pronostici.py
- frontend/gui/pages/03_Crea_Bolletta.py
- frontend/gui/pages/04_Telegram_Channel.py
- frontend/gui/pages/05_Classifica_Tipster.py
- frontend/gui/pages/99_Settings.py
- frontend/gui/components/common.py
- .streamlit/config.toml
- scripts/fetch_results_football_data.py
- scripts/predict_elo_fdo.py
- scripts/fetch_odds_oddsapi.py
- scripts/telegram_ingest.py
- scripts/telegram_resolve_results.py
- data/aliases/teams.json (seed base)
- docs/PR_PLAN.md (questo file)

Modifiche
- backend/api/main.py (registrazione nuovi router)
- frontend/gui/streamlit_app.py (navigazione pagine + brand)
- requirements.txt / frontend/gui/requirements.txt (aggiunta: requests, telethon, rapidfuzz, python-dotenv, pydantic se manca)
- .vscode/tasks.json (nuovi task)
- .gitignore (assicurare .env, data/*.db non committati)

---

Dipendenze nuove
- requests
- telethon
- rapidfuzz
- python-dotenv
- pydantic (se non già presente a livello backend)
- sqlalchemy (facoltativo per SQLite, in alternativa uso sqlite3 standard + pandas)

---

Canali Telegram — seed iniziale
- In questa PR includeremo un seed iniziale di tipster italiani (calcio) pre-popolato nella pagina Telegram Channel e nel DB locale.
- Se vuoi limitazioni (solo free, solo canali pubblici, no gruppi privati), specifica ora.

---

Milestone e ordine di sviluppo (nella stessa PR)

1) Base Dati & Odds
   - fetch_results_football_data.py
   - predict_elo_fdo.py
   - fetch_odds_oddsapi.py
   - value picks generation (server-side)

2) Backend API
   - /events, /predictions, /odds, /value-picks
   - /betslip/suggest (greedy)
   - /settings (get/set .env)

3) GUI Streamlit
   - 01_Eventi, 02_Pronostici, 03_Crea_Bolletta, 99_Settings
   - Theming e componenti comuni

4) Telegram (MVP)
   - telegram_ingest.py, telegram_resolve_results.py
   - /tipsters, /tipsters/leaderboard
   - 04_Telegram_Channel, 05_Classifica_Tipster

5) Rifiniture
   - Alias team e matching robusto
   - Miglioramenti UX (loader, empty-states, badge)
   - Documentazione README/How-to

---

Criteri di accettazione
- Eventi mostra fixtures per range (1/2/7), raggruppati per lega, con best odds 1X2.
- Settings salva e legge correttamente le chiavi da .env e permette test provider.
- Pronostici mostra probabilità modello, fair odds e value picks filtrabili per edge.
- Crea Bolletta propone almeno una combinazione coerente con la quota target.
- Telegram consente l’aggiunta di canali, l’ingestione dei messaggi e la vista storica dei picks; Classifica calcola ranking base per periodo.

---

Rischi & Mitigazioni
- Limiti free dei provider odds: soluzione con fallback e caching locale; possibilità di passare a provider alternativo.
- Parsing Telegram non standardizzato: parser a pattern incrementali e feedback loop in logs.
- Matching cross-provider: introduciamo alias e fuzzy con soglie conservative; log errori per correzioni manuali.

---

Prossimi step per approvazione
- Confermi il piano e l’uso di The Odds API per le quote.
- Vuoi che pre-popoliamo i canali tipster italiani (seed)? Indica eventuali esclusioni.
- Posso procedere a generare tutti i file elencati (backend, GUI, scripts, tasks) per la PR unica?

```diff
+ Dopo il tuo OK e il push di docs/PR_PLAN.md sul branch "optimize", fornirò TUTTI i file completi da copiare e incollare.
```
