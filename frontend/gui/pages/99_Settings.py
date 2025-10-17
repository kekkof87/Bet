import os
import requests
import streamlit as st

API_URL = os.environ.get("API_URL")

st.set_page_config(page_title="Settings", layout="wide")
st.title("Settings")

if not API_URL:
    st.error("API_URL non impostata. Avvia la API o imposta la variabile in Tasks → GUI: Run Streamlit.")
    st.stop()

# Visualizza stato
r = requests.get(f"{API_URL}/settings", timeout=20)
r.raise_for_status()
cfg = r.json()
st.subheader("Stato attuale")
st.json(cfg)

st.subheader("Aggiorna chiavi e parametri")
with st.form("settings_form"):
    col1, col2 = st.columns(2)
    with col1:
        FOOTBALL_DATA_API_KEY = st.text_input("FOOTBALL_DATA_API_KEY", value="")
        ODDS_API_KEY = st.text_input("ODDS_API_KEY", value="")
        TELEGRAM_API_ID = st.text_input("TELEGRAM_API_ID", value="")
    with col2:
        TELEGRAM_API_HASH = st.text_input("TELEGRAM_API_HASH", value="")
        TIMEZONE = st.text_input("TIMEZONE", value="Europe/Rome")
        FETCH_DAYS = st.text_input("FETCH_DAYS", value="7")
        LEAGUE_CODES = st.text_input("LEAGUE_CODES", value="")
        EFFECTIVE_THRESHOLD = st.text_input("EFFECTIVE_THRESHOLD", value="0.03")
    submitted = st.form_submit_button("Salva")
    if submitted:
        updates = {}
        for k, v in {
            "FOOTBALL_DATA_API_KEY": FOOTBALL_DATA_API_KEY,
            "ODDS_API_KEY": ODDS_API_KEY,
            "TELEGRAM_API_ID": TELEGRAM_API_ID,
            "TELEGRAM_API_HASH": TELEGRAM_API_HASH,
            "TIMEZONE": TIMEZONE,
            "FETCH_DAYS": FETCH_DAYS,
            "LEAGUE_CODES": LEAGUE_CODES,
            "EFFECTIVE_THRESHOLD": EFFECTIVE_THRESHOLD,
        }.items():
            if v:
                updates[k] = v
        rr = requests.post(f"{API_URL}/settings", json=updates, timeout=25)
        if rr.ok:
            st.success("Impostazioni salvate. Riavvia i task/GUI se necessario.")
        else:
            st.error(f"Errore salvataggio: {rr.status_code} {rr.text}")
