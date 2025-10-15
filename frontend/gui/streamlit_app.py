import os
import json
from pathlib import Path
from typing import Optional, Dict, Any  # removed: List

import streamlit as st
import pandas as pd
import altair as alt
import requests

API_URL = os.environ.get("API_URL")  # es: http://localhost:8000
DATA_DIR = Path(os.environ.get("DATA_DIR", "data")).resolve()

st.set_page_config(page_title="Betting Dashboard", layout="wide")

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

st.sidebar.title("Navigazione")
page = st.sidebar.radio("Vai a", ["Alerts", "Predictions", "Fixtures", "ROI"])

if page == "Alerts":
    st.title("Value Alerts")
    data = fetch("/alerts", fallback_file="value_alerts.json")
    df = to_dataframe(data)
    st.dataframe(df, use_container_width=True)
    download_button(df, "alerts.csv")

elif page == "Predictions":
    st.title("Predictions")
    min_edge = st.sidebar.slider("Min edge", 0.0, 0.2, 0.03, 0.005)
    active_only = st.sidebar.checkbox("Solo active", value=False)
    # Polishing: default status=NS
    status = st.sidebar.multiselect("Status", ["NS","1H","HT","2H","FT","PST"], default=["NS"])
    params = {"min_edge": min_edge, "active_only": active_only, "status": status}
    data = fetch("/predictions", fallback_file="latest_predictions.json", params=params)
    df = to_dataframe(data, key="items")
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
    st.dataframe(df, use_container_width=True)
    download_button(df, "fixtures.csv")

elif page == "ROI":
    st.title("ROI")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Metrics")
        metrics = fetch("/roi/metrics", fallback_file="roi_metrics.json")
        st.json(metrics)
        # Download metrics
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
        # Chart semplice se presenti colonne standard: date, roi
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
