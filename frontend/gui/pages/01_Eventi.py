import os
import json
from pathlib import Path

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
items = []

if API_URL:
    try:
        r = requests.get(f"{API_URL}/events", params=params, timeout=25)
        r.raise_for_status()
        data = r.json()
        items = data.get("items", [])
    except Exception as e:
        st.warning(f"Chiamata API /events fallita, uso fallback file: {e}")

if not items:
    # fallback: legge correttamente JSON dal file fixtures.json
    p = DATA_DIR / "fixtures.json"
    if not p.exists():
        st.error("fixtures.json non trovato. Esegui il task: 'Fetch fixtures (Football-Data.org)'.")
        st.stop()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        items = raw.get("items", raw) if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            items = []
    except Exception as e:
        st.error(f"Errore lettura fixtures.json: {e}")
        st.stop()

df = pd.json_normalize(items)
if df.empty:
    st.warning("Nessun evento nel periodo selezionato.")
    st.stop()

df = add_status_badge(df, col="status")

# Raggruppa per lega
leagues = sorted([x for x in df["league"].dropna().unique().tolist()]) if "league" in df.columns else []
lg_selected = st.multiselect("Filtra Leghe", leagues, default=leagues[:10] if leagues else [])
if lg_selected:
    df = df[df["league"].isin(lg_selected)]

# Miglior quota (se presente in best_odds)
if "best_odds.home" in df.columns or "best_odds" in df.columns:
    # normalizza colonna best
    if "best_odds.home" not in df.columns and "best_odds" in df.columns:
        try:
            best = pd.json_normalize(df["best_odds"]).add_prefix("best_odds.")
            df = pd.concat([df.drop(columns=["best_odds"]), best], axis=1)
        except Exception:
            pass

# Visualizza per lega (o tutto se lega mancante)
if "league" in df.columns:
    for lg in sorted(df["league"].dropna().unique().tolist()):
        sub = df[df["league"] == lg].copy()
        st.subheader(lg)
        cols_show = [c for c in ["state","kickoff","home","away","status","best_odds.home","best_odds.draw","best_odds.away","best_odds.book"] if c in sub.columns]
        st.dataframe(sub[cols_show].sort_values("kickoff") if "kickoff" in sub.columns else sub[cols_show], use_container_width=True)
else:
    st.dataframe(df, use_container_width=True)
