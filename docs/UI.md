# GUI rapida (Streamlit)

## Avvio locale
```bash
pip install streamlit
streamlit run ui/app.py
```

Per default legge i file dalla cartella `data/`. Cambia il path dalla UI in alto se necessario.

## Cosa mostra
- Fixtures latest (tab Fixtures)
- Odds latest (tab Odds) — provider “model” o “stub”
- Predictions (tab Predictions) — evidenzia value edge
- ROI metrics (tab ROI)

Consuma i JSON generati dalla pipeline (fixtures → odds → predictions → ROI).
