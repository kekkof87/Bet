import os
import requests
import streamlit as st
import pandas as pd

API_URL = os.environ.get("API_URL")

st.set_page_config(page_title="Classifica Tipster", layout="wide")
st.title("Classifica Tipster")

range_days = st.selectbox("Periodo", [7, 30, 90, 180], index=2)
if API_URL:
    r = requests.get(f"{API_URL}/tipsters/leaderboard", params={"range_days": int(range_days)}, timeout=25)
    r.raise_for_status()
    data = r.json()
else:
    st.error("Per la leaderboard serve l’API attiva.")
    st.stop()

df = pd.json_normalize(data.get("items", []))
if df.empty:
    st.info("Nessun dato per la classifica.")
else:
    st.dataframe(df.sort_values(["roi","hit_rate","picks"], ascending=[False,False,False]), use_container_width=True)
