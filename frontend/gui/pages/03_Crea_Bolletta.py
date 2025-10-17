import os
import requests
import streamlit as st
import pandas as pd
from pathlib import Path

API_URL = os.environ.get("API_URL")
DATA_DIR = Path(os.environ.get("DATA_DIR", "data")).resolve()

st.set_page_config(page_title="Crea Bolletta", layout="wide")
st.title("Crea Bolletta")

target_odds = st.number_input("Quota totale target", min_value=1.1, value=5.0, step=0.1)
min_picks = int(st.number_input("Min eventi", min_value=1, value=2, step=1))
max_picks = int(st.number_input("Max eventi", min_value=1, value=6, step=1))
edge_min = st.slider("Soglia edge minimo", 0.0, 0.2, 0.03, 0.005)

if st.button("Suggerisci combinazioni"):
    if not API_URL:
        st.error("API_URL non impostata, abilita API per la proposta bolletta.")
        st.stop()
    r = requests.post(f"{API_URL}/betslip/suggest", json={
        "target_odds": float(target_odds),
        "min_picks": int(min_picks),
        "max_picks": int(max_picks),
        "edge_min": float(edge_min),
    }, timeout=30)
    r.raise_for_status()
    data = r.json()
    st.subheader("Combinazione primaria")
    primary = data.get("primary", {})
    df1 = pd.json_normalize(primary.get("combo", []))
    st.write(f"Quota stimata: {primary.get('combo_odds', 1.0):.2f}")
    st.dataframe(df1, use_container_width=True)

    st.subheader("Alternative")
    for alt in data.get("alternatives", []):
        df = pd.json_normalize(alt.get("combo", []))
        st.write(f"Quota stimata: {alt.get('combo_odds', 1.0):.2f}")
        st.dataframe(df, use_container_width=True)
