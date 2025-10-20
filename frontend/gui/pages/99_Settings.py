import os
from pathlib import Path
import json
import requests
import streamlit as st

from dotenv import find_dotenv, load_dotenv, set_key

API_URL = os.environ.get("API_URL")
DATA_DIR = Path(os.environ.get("DATA_DIR", "data")).resolve()

st.set_page_config(page_title="Settings", layout="wide")
st.title("Settings")

def mask(v: str | None) -> str:
    if not v:
        return "(none)"
    v = str(v)
    return v[:4] + "…" if len(v) > 4 else v

def read_env_map() -> dict:
    p = find_dotenv(usecwd=True)
    if p:
        load_dotenv(p, override=False)
    return {
        "FOOTBALL_DATA_API_KEY": os.getenv("FOOTBALL_DATA_API_KEY"),
        "ODDS_API_KEY": os.getenv("ODDS_API_KEY"),
        "TELEGRAM_API_ID": os.getenv("TELEGRAM_API_ID"),
        "TELEGRAM_API_HASH": os.getenv("TELEGRAM_API_HASH"),
        "TIMEZONE": os.getenv("TIMEZONE", "Europe/Rome"),
        "FETCH_DAYS": os.getenv("FETCH_DAYS", "7"),
        "LEAGUE_CODES": os.getenv("LEAGUE_CODES", ""),
        "EFFECTIVE_THRESHOLD": os.getenv("EFFECTIVE_THRESHOLD", "0.03"),
        "DATA_DIR": os.getenv("DATA_DIR", "./data"),
    }

def write_env_map(updates: dict) -> tuple[bool, str]:
    p = find_dotenv(usecwd=True)
    if not p:
        # crea un nuovo .env nella root del progetto
        p = str((Path(__file__).resolve().parents[3] / ".env"))
    try:
        for k, v in updates.items():
            if isinstance(v, str):
                set_key(p, k, v, quote_mode="never")
                os.environ[k] = v
        return True, p
    except Exception as e:
        return False, str(e)

tab1, tab2 = st.tabs(["Server (API)", "Locale (.env)"])

with tab1:
    st.subheader("Impostazioni lato API")
    if not API_URL:
        st.warning("API_URL non impostata. Avvia la API o usa la scheda 'Locale (.env)'.")
    else:
        try:
            r = requests.get(f"{API_URL}/settings", timeout=20)
            r.raise_for_status()
            cfg = r.json()
            st.json(cfg)
            st.markdown("Aggiorna parametri lato server:")
            with st.form("server_form"):
                FOOTBALL_DATA_API_KEY = st.text_input("FOOTBALL_DATA_API_KEY", value="")
                ODDS_API_KEY = st.text_input("ODDS_API_KEY", value="")
                TELEGRAM_API_ID = st.text_input("TELEGRAM_API_ID", value="")
                TELEGRAM_API_HASH = st.text_input("TELEGRAM_API_HASH", value="")
                TIMEZONE = st.text_input("TIMEZONE", value="Europe/Rome")
                FETCH_DAYS = st.text_input("FETCH_DAYS", value="7")
                LEAGUE_CODES = st.text_input("LEAGUE_CODES", value="")
                EFFECTIVE_THRESHOLD = st.text_input("EFFECTIVE_THRESHOLD", value="0.03")
                submitted = st.form_submit_button("Salva lato server")
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
                        st.success("Impostazioni salvate sul server.")
                    else:
                        st.error(f"Errore salvataggio server: {rr.status_code} {rr.text}")
        except Exception as e:
            st.error(f"Errore contattando l'API: {e}")

with tab2:
    st.subheader("Impostazioni locali (.env)")
    envmap = read_env_map()
    st.write("Valori attuali (mascherati per le chiavi):")
    st.json({k: (mask(v) if "KEY" in k or "HASH" in k or "ID" in k else v) for k, v in envmap.items()})

    st.markdown("Aggiorna .env locale:")
    with st.form("local_form"):
        FOOTBALL_DATA_API_KEY_L = st.text_input("FOOTBALL_DATA_API_KEY", value=envmap.get("FOOTBALL_DATA_API_KEY") or "")
        ODDS_API_KEY_L = st.text_input("ODDS_API_KEY", value=envmap.get("ODDS_API_KEY") or "")
        TELEGRAM_API_ID_L = st.text_input("TELEGRAM_API_ID", value=envmap.get("TELEGRAM_API_ID") or "")
        TELEGRAM_API_HASH_L = st.text_input("TELEGRAM_API_HASH", value=envmap.get("TELEGRAM_API_HASH") or "")
        TIMEZONE_L = st.text_input("TIMEZONE", value=envmap.get("TIMEZONE") or "Europe/Rome")
        FETCH_DAYS_L = st.text_input("FETCH_DAYS", value=envmap.get("FETCH_DAYS") or "7")
        LEAGUE_CODES_L = st.text_input("LEAGUE_CODES", value=envmap.get("LEAGUE_CODES") or "")
        EFFECTIVE_THRESHOLD_L = st.text_input("EFFECTIVE_THRESHOLD", value=envmap.get("EFFECTIVE_THRESHOLD") or "0.03")
        DATA_DIR_L = st.text_input("DATA_DIR", value=envmap.get("DATA_DIR") or "./data")
        submitted_local = st.form_submit_button("Salva .env locale")
        if submitted_local:
            updates = {
                "FOOTBALL_DATA_API_KEY": FOOTBALL_DATA_API_KEY_L,
                "ODDS_API_KEY": ODDS_API_KEY_L,
                "TELEGRAM_API_ID": TELEGRAM_API_ID_L,
                "TELEGRAM_API_HASH": TELEGRAM_API_HASH_L,
                "TIMEZONE": TIMEZONE_L,
                "FETCH_DAYS": FETCH_DAYS_L,
                "LEAGUE_CODES": LEAGUE_CODES_L,
                "EFFECTIVE_THRESHOLD": EFFECTIVE_THRESHOLD_L,
                "DATA_DIR": DATA_DIR_L,
            }
            ok, info = write_env_map(updates)
            if ok:
                st.success(f".env aggiornato: {info}")
            else:
                st.error(f"Errore scrittura .env: {info}")
