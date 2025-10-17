import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import streamlit as st
import pandas as pd
import requests

from frontend.gui.components.common import add_status_badge

API_URL = os.environ.get("API_URL")
DATA_DIR = Path(os.environ.get("DATA_DIR", "data")).resolve()

st.set_page_config(page_title="Eventi", layout="wide")
st.title("Eventi")

rng = st.radio("Periodo", ["Oggi", "Prossimi 2 giorni", "Prossimi 7 giorni"], horizontal=True)
range_days = {"Oggi": 1, "Prossimi 2 giorni": 2, "Prossimi 7 giorni": 7}[rng]

params = {"range_days": range_days}
if API_URL:
    r = requests.get(f"{API_URL}/events", params=params, timeout=25)
    r.raise_for_status()
    data = r.json()
else:
    # fallback: legge fixtures.json e non mostra best_odds
    p = DATA_DIR / "fixtures.json"
    if not p.exists():
        st.error("fixtures.json non trovato. Esegui il fetch fixtures.")
        st.stop()
    data = {"items": (p.read_text())}

items = data.get("items", [])
df = pd.json_normalize(items)
if df.empty:
    st.warning("Nessun evento nel periodo selezionato.")
    st.stop()

df = add_status_badge(df, col="status")

# Raggruppa per lega
leagues = sorted([x for x in df["league"].dropna().unique().tolist()])
lg_selected = st.multiselect("Filtra Leghe", leagues, default=leagues[:10])
if lg_selected:
    df = df[df["league"].isin(lg_selected)]

# Miglior quota (se presente in best_odds)
def best_col(b: Optional[Dict[str, Any]], k: str) -> float:
    try:
        return float((b or {}).get(k) or 0.0)
    except Exception:
        return 0.0

if "best_odds.home" in df.columns or "best_odds" in df.columns:
    # normalizza colonna best
    if "best_odds.home" not in df.columns and "best_odds" in df.columns:
        best = pd.json_normalize(df["best_odds"]).add_prefix("best_odds.")
        df = pd.concat([df.drop(columns=["best_odds"]), best], axis=1)

# Visualizza per lega
for lg in sorted(df["league"].dropna().unique().tolist()):
    sub = df[df["league"] == lg].copy()
    st.subheader(lg)
    cols_show = [c for c in ["state","kickoff","home","away","status","best_odds.home","best_odds.draw","best_odds.away","best_odds.book"] if c in sub.columns]
    st.dataframe(sub[cols_show].sort_values("kickoff"), use_container_width=True)
