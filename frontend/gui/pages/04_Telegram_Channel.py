import os
import json
from pathlib import Path
import streamlit as st
import pandas as pd
import requests

API_URL = os.environ.get("API_URL")
DATA_DIR = Path(os.environ.get("DATA_DIR", "data")).resolve()

st.set_page_config(page_title="Telegram channel", layout="wide")
st.title("Telegram channel")

def fetch_tipsters():
    if API_URL:
        try:
            r = requests.get(f"{API_URL}/tipsters", timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            st.warning(f"API /tipsters non raggiungibile: {e}")
    p = DATA_DIR / "telegram" / "tipsters.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    seed = DATA_DIR / "telegram" / "tipsters_seed.json"
    if seed.exists():
        try:
            return json.loads(seed.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"items": []}

tipsters = fetch_tipsters().get("items", [])
df_t = pd.json_normalize(tipsters)
if df_t.empty:
    st.info("Nessun tipster configurato. Aggiungili in Settings o via file data/telegram/tipsters.json")
else:
    st.subheader("Elenco Tipster")
    st.dataframe(df_t, use_container_width=True)

# Picks per tipster (se presenti)
picks_path = DATA_DIR / "telegram" / "picks.jsonl"
if picks_path.exists():
    items = []
    try:
        with picks_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
    except Exception as e:
        st.error(f"Errore lettura picks.jsonl: {e}")
        items = []
    if items:
        df = pd.json_normalize(items)
        st.subheader("Picks recenti")
        st.dataframe(df, use_container_width=True)
else:
    st.info("Nessun picks.jsonl presente. Esegui l’ingest Telegram quando avrai API_ID/API_HASH.")
