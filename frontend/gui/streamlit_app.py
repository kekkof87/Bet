import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

import streamlit as st
import pandas as pd
import altair as alt
import requests
from datetime import datetime

# Config di base
API_URL = os.environ.get("API_URL")  # es: http://localhost:8000
DATA_DIR = Path(os.environ.get("DATA_DIR", "data")).resolve()

st.set_page_config(page_title="Betting Dashboard", layout="wide")

# ---------------------------
# Helper condivisi (cache/file/API)
# ---------------------------
@st.cache_data(ttl=10)
def _load_file(path: Path) -> Any:
    if path.suffix == ".jsonl":
        items = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        items.append(json.loads(line))
                    except Exception:
                        items.append({"raw": line})
        return {"count": len(items), "items": items}
    else:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

@st.cache_data(ttl=10)
def fetch(endpoint: str, fallback_file: Optional[str] = None, params: Optional[Dict[str, Any]] = None):
    if API_URL:
        r = requests.get(f"{API_URL}{endpoint}", params=params or {}, timeout=20)
        r.raise_for_status()
        return r.json()
    if not fallback_file:
        st.error("Nessuna API_URL e nessun file di fallback impostato.")
        st.stop()
    path = DATA_DIR / fallback_file
    if not path.exists():
        st.error(f"File non trovato: {path}")
        st.stop()
    return _load_file(path)

def to_dataframe(obj: Any, key: Optional[str] = None) -> pd.DataFrame:
    if isinstance(obj, dict) and key and key in obj:
        data = obj[key]
    elif isinstance(obj, dict) and "items" in obj:
        data = obj["items"]
    else:
        data = obj
    try:
        return pd.json_normalize(data)
    except Exception:
        return pd.DataFrame(data)

def download_button(df: pd.DataFrame, filename: str, label: str = "Download CSV"):
    csv = df.to_csv(index=False)
    st.download_button(label=label, data=csv.encode("utf-8"), file_name=filename, mime="text/csv")

def add_live_badge(df: pd.DataFrame, status_col_candidates = ("status","fixture.status")) -> pd.DataFrame:
    # Prova a trovare la colonna status anche se annidata
    status_col = None
    for c in status_col_candidates:
        if c in df.columns:
            status_col = c
            break
    if status_col is None:
        return df
    def badge(s: Any) -> str:
        s_up = str(s).upper()
        if s_up in {"1H", "HT", "2H"}:
            return "🟢 LIVE"
        if s_up == "NS":
            return "🕒"
        if s_up == "FT":
            return "🏁"
        if s_up == "PST":
            return "⏸️"
        return ""
    out = df.copy()
    out.insert(0, "state", out[status_col].apply(badge))
    return out

def _switch_to(page_path: str):
    # Naviga alla multipage se disponibile (Streamlit >=1.22 supporta st.switch_page)
    try:
        st.switch_page(page_path)
    except Exception:
        st.info(f"Pagina non trovata: {page_path}. Assicurati esista in frontend/gui/pages/.")

# ---------------------------
# Sidebar: navigazione + auto-refresh + link alle pagine
# ---------------------------
st.sidebar.title("Navigazione")
page = st.sidebar.radio(
    "Vai a",
    [
        "Home",
        "Alerts",
        "Predictions",
        "Fixtures",
        "Odds",
        "ROI",
        "➡️ Eventi (pagina)",
        "➡️ Pronostici (pagina)",
        "➡️ Crea Bolletta (pagina)",
        "➡️ Telegram channel (pagina)",
        "➡️ Classifica Tipster (pagina)",
        "➡️ Settings (pagina)"
    ],
    index=0
)
refresh_s = st.sidebar.number_input(
    "Auto-refresh (sec)", min_value=0, max_value=300, value=0, step=5, help="0 = disabilitato"
)

if refresh_s and refresh_s > 0:
    # Best-effort per invalidare cache/forzare refresh
    st.sidebar.write(f"Aggiorna ogni {refresh_s}s (se non vedi aggiornamenti, ricarica manualmente)")
    st.experimental_set_query_params(_ts=int(datetime.utcnow().timestamp()))

# ---------------------------
# HOME: landing con stato e collegamenti rapidi
# ---------------------------
if page == "Home":
    st.title("Betting Dashboard")
    colA, colB, colC = st.columns(3)
    with colA:
        st.metric("API_URL", API_URL or "(non impostata)")
        st.metric("DATA_DIR", str(DATA_DIR))
    with colB:
        try:
            if API_URL:
                h = requests.get(f"{API_URL}/health", timeout=10).json()
                st.success(f"API ok • data_dir: {h.get('data_dir')}")
            else:
                st.warning("API_URL non impostata")
        except Exception as e:
            st.error(f"API non raggiungibile: {e}")
    with colC:
        st.write("Azioni rapide")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Apri Eventi"):
                _switch_to("frontend/gui/pages/01_Eventi.py")
            if st.button("Apri Pronostici"):
                _switch_to("frontend/gui/pages/02_Pronostici.py")
            if st.button("Apri Crea Bolletta"):
                _switch_to("frontend/gui/pages/03_Crea_Bolletta.py")
        with c2:
            if st.button("Apri Telegram"):
                _switch_to("frontend/gui/pages/04_Telegram_Channel.py")
            if st.button("Apri Classifica Tipster"):
                _switch_to("frontend/gui/pages/05_Classifica_Tipster.py")
            if st.button("Apri Settings"):
                _switch_to("frontend/gui/pages/99_Settings.py")

    st.markdown("---")
    st.subheader("Checklist dati")
    st.markdown("- Fixtures reali (FDO): data/fixtures.json")
    st.markdown("- Risultati storici (FDO): data/history/results.jsonl")
    st.markdown("- Predizioni: data/latest_predictions.json")
    st.markdown("- Quote (The Odds API): data/odds_latest.json")
    st.markdown("- Value picks: data/value_picks.json")

# ---------------------------
# SEZIONI LEGACY (restano disponibili qui)
# ---------------------------
elif page == "Alerts":
    st.title("Value Alerts")
    data = fetch("/alerts", fallback_file="value_alerts.json")
    df = to_dataframe(data)
    if "edge" in df.columns:
        df["edge"] = pd.to_numeric(df["edge"], errors="coerce")
        df = df.sort_values("edge", ascending=False)
    df = add_live_badge(df, status_col_candidates=("status","fixture.status"))
    st.dataframe(df, use_container_width=True)
    download_button(df, "alerts.csv")

elif page == "Predictions":
    st.title("Predictions")
    min_edge = st.sidebar.slider("Min edge", 0.0, 0.2, 0.03, 0.005)
    active_only = st.sidebar.checkbox("Solo active", value=False)
    # Default status=NS
    status = st.sidebar.multiselect("Status", ["NS","1H","HT","2H","FT","PST"], default=["NS"])
    only_value = st.sidebar.checkbox("Solo value (edge >= min_edge)", value=True)
    params = {"min_edge": min_edge if only_value else None, "active_only": active_only, "status": status}
    data = fetch("/predictions", fallback_file="latest_predictions.json", params=params)
    df = to_dataframe(data, key="items")
    if "edge" in df.columns:
        df["edge"] = pd.to_numeric(df["edge"], errors="coerce")
        if only_value:
            df = df[df["edge"] >= float(min_edge)]
        df = df.sort_values("edge", ascending=False)
    df = add_live_badge(df, status_col_candidates=("status","fixture.status"))
    st.dataframe(df, use_container_width=True)
    download_button(df, "predictions.csv")

elif page == "Fixtures":
    st.title("Fixtures")
    status = st.sidebar.multiselect("Status", ["NS","1H","HT","2H","FT","PST"], default=None)
    params = {"status": status} if status else None
    data = fetch("/fixtures", fallback_file="fixtures.json", params=params)
    # fallback a last_delta se fixtures.json non presente
    if isinstance(data, dict) and "items" not in data and "added" in data:
        data = {"items": data["added"]}
    df = to_dataframe(data, key="items")
    df = add_live_badge(df, status_col_candidates=("status",))
    st.dataframe(df, use_container_width=True)
    download_button(df, "fixtures.csv")

elif page == "Odds":
    st.title("Odds")
    raw = fetch("/odds", fallback_file="odds_latest.json")
    df = to_dataframe(raw)
    # Normalizza colonne comuni se necessario
    rename_map = {
        "price": "odds",
        "decimal": "odds",
        "book": "bookmaker",
        "bk": "bookmaker",
        "market_code": "market",
        "outcome": "selection",
        "pick": "selection",
    }
    for k, v in rename_map.items():
        if k in df.columns and v not in df.columns:
            df[v] = df[k]
    # Filtri
    market_options = sorted(df["market"].dropna().unique().tolist()) if "market" in df.columns else []
    bookmaker_options = sorted(df["bookmaker"].dropna().unique().tolist()) if "bookmaker" in df.columns else []
    selection_options = sorted(df["selection"].dropna().unique().tolist()) if "selection" in df.columns else []
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        market = st.selectbox("Market", options=["(tutti)"] + market_options, index=0)
    with col2:
        bookmaker = st.selectbox("Bookmaker", options=["(tutti)"] + bookmaker_options, index=0)
    with col3:
        selection = st.selectbox("Selection", options=["(tutti)"] + selection_options, index=0)
    with col4:
        min_odds = st.number_input("Min odds", min_value=0.0, value=0.0, step=0.05)
    # Applica filtri lato client
    if "market" in df.columns and market != "(tutti)":
        df = df[df["market"] == market]
    if "bookmaker" in df.columns and bookmaker != "(tutti)":
        df = df[df["bookmaker"] == bookmaker]
    if "selection" in df.columns and selection != "(tutti)":
        df = df[df["selection"] == selection]
    if "odds" in df.columns:
        df["odds"] = pd.to_numeric(df["odds"], errors="coerce")
        df = df[df["odds"] >= float(min_odds)]
        df = df.sort_values("odds", ascending=False)
    st.dataframe(df, use_container_width=True)
    download_button(df, "odds.csv")

elif page == "ROI":
    st.title("ROI")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Metrics")
        metrics = fetch("/roi/metrics", fallback_file="roi_metrics.json")
        st.json(metrics)
        df_metrics = pd.json_normalize(metrics)
        download_button(df_metrics, "roi_metrics.csv", label="Download metrics CSV")
    with col2:
        st.subheader("Daily")
        daily = fetch("/roi/daily", fallback_file="roi_daily.json")
        df_daily = to_dataframe(daily)
        st.dataframe(df_daily, use_container_width=True)
        download_button(df_daily, "roi_daily.csv", label="Download daily CSV")
    st.subheader("History")
    hist = fetch("/roi/history", fallback_file="roi_history.jsonl")
    df_hist = to_dataframe(hist, key="items")
    if not df_hist.empty:
        for date_col in ["date", "day", "timestamp", "generated_at"]:
            if date_col in df_hist.columns:
                df_hist[date_col] = pd.to_datetime(df_hist[date_col], errors="coerce")
        num_cols = [c for c in df_hist.columns if c.lower() in ["roi", "cum_roi", "yield", "bankroll", "profit_sum"] or c.endswith("roi")]
        if num_cols:
            date_col = next((c for c in ["date","day","timestamp","generated_at"] if c in df_hist.columns), None)
            if date_col:
                chart = (
                    alt.Chart(df_hist).mark_line().encode(
                        x=alt.X(date_col, title="Date"),
                        y=alt.Y(num_cols[0], title=num_cols[0]),
                        tooltip=[date_col] + num_cols
                    ).interactive()
                )
                st.altair_chart(chart, use_container_width=True)
    st.dataframe(df_hist, use_container_width=True)
    download_button(df_hist, "roi_history.csv", label="Download history CSV")

# ---------------------------
# Scorciatoie alle pagine multipage
# ---------------------------
elif page == "➡️ Eventi (pagina)":
    _switch_to("frontend/gui/pages/01_Eventi.py")

elif page == "➡️ Pronostici (pagina)":
    _switch_to("frontend/gui/pages/02_Pronostici.py")

elif page == "➡️ Crea Bolletta (pagina)":
    _switch_to("frontend/gui/pages/03_Crea_Bolletta.py")

elif page == "➡️ Telegram channel (pagina)":
    _switch_to("frontend/gui/pages/04_Telegram_Channel.py")

elif page == "➡️ Classifica Tipster (pagina)":
    _switch_to("frontend/gui/pages/05_Classifica_Tipster.py")

elif page == "➡️ Settings (pagina)":
    _switch_to("frontend/gui/pages/99_Settings.py")
