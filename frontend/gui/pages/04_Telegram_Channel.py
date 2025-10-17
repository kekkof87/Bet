import os
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
        r = requests.get(f"{API_URL}/tipsters", timeout=20)
        r.raise_for_status()
        return r.json()
    p = DATA_DIR / "telegram" / "tipsters.json"
    if p.exists():
        return pd.read_json(p).to_dict()
    seed = DATA_DIR / "telegram" / "tipsters_seed.json"
    if seed.exists():
        return pd.read_json(seed).to_dict()
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
    with picks_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(pd.json.loads(line) if hasattr(pd, "json") else __import__("json").loads(line))
    df = pd.json_normalize(items)
    st.subheader("Picks recenti")
    st.dataframe(df, use_container_width=True)
else:
    st.info("Nessun picks.jsonl presente. Esegui l’ingest Telegram quando avrai API_ID/API_HASH.")
