# Setup provider gratuito (football-data.org)

## 1) Crea la chiave
- Registrati gratis: https://www.football-data.org/client/register
- Copia la API key.

## 2) Aggiungi il secret al repository
- Settings → Secrets and variables → Actions → New repository secret
  - Name: `FOOTBALL_DATA_API_KEY`
  - Value: la tua key

## 3) Aggiungi le variabili (Settings → Secrets and variables → Actions → Variables)
- `PROVIDER_SOURCE=fd`
- `FOOTBALL_DATA_LEAGUES=PL,BL1,SA,PD,FL1,CL,EL,ECL`
- `UPCOMING_DAYS=2`
- (opzionale) `BET_DATA_DIR=data`

## 4) Esecuzione
- Tab Actions → “Fetch Pipeline” → Run workflow.
- I file generati saranno in `data/`:
  - `fixtures_latest.json`
  - `scoreboard.json`
  - `metrics/last_run.json`
  - (se avvii anche `scripts/fetch_odds.py` o un workflow che lo esegue) `data/odds/odds_latest.json` (provider `model`)

## Note
- Puoi tornare ad API-Football impostando `PROVIDER_SOURCE=api`.
- Le odds sono fair odds “model-based” (gratis) e hanno lo stesso formato della stub esistente.
