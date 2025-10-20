import os
from pathlib import Path
import streamlit as st
import pandas as pd
import requests

from frontend.gui.components.common import add_status_badge, edge_color

API_URL = os.environ.get("API_URL")
DATA_DIR = Path(os.environ.get("DATA_DIR", "data")).resolve()

st.set_page_config(page_title="Pronostici", layout="wide")
st.title("Pronostici")

edge_min = st.slider("Soglia edge minimo", 0.0, 0.2, 0.03, 0.005)

data = None
if API_URL:
    try:
        r = requests.get(f"{API_URL}/value-picks", params={"edge_min": edge_min}, timeout=25)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        st.warning(f"Chiamata API /value-picks fallita ({e}). Uso fallback file se presente.")

if data is None:
    p = DATA_DIR / "value_picks.json"
    if not p.exists():
        st.error("value_picks.json non trovato. Esegui i task: 'Fetch fixtures', 'Fetch results', 'Predictions: Elo (FDO)', 'Fetch odds (The Odds API)' e poi 'Generate value picks (offline)'. Oppure avvia la API e ricarica.")
        st.stop()
    try:
        data = pd.read_json(p)
        if isinstance(data, pd.DataFrame):
            data = data.to_dict()
    except Exception as e:
        st.error(f"Errore lettura value_picks.json: {e}")
        st.stop()

items = data.get("items", [])
df = pd.json_normalize(items)
if df.empty:
    st.info("Nessun value pick con la soglia corrente.")
    st.stop()

df["edge"] = pd.to_numeric(df["edge"], errors="coerce")
df["badge"] = df["edge"].apply(lambda x: edge_color(float(x)))
df = add_status_badge(df, col="status")
cols = ["badge","state","kickoff","league","home","away","pick","prob","fair_odds","best_odds","edge","book","model"]
cols = [c for c in cols if c in df.columns]
st.dataframe(df[cols].sort_values("edge", ascending=False), use_container_width=True)
