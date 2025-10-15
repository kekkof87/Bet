from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> None:
    st.set_page_config(page_title="Bet Dashboard", layout="wide")
    st.title("Bet Dashboard")

    data_dir = Path(st.text_input("Data directory", "data")).resolve()

    tabs = st.tabs(["Fixtures", "Odds", "Predictions", "ROI"])

    # Fixtures
    with tabs[0]:
        fx_path = data_dir / "fixtures_latest.json"
        st.subheader("Fixtures latest")
        if fx_path.exists():
            fx = _load_json(fx_path) or []
            st.write(f"Count: {len(fx)}")
            st.dataframe(fx, use_container_width=True)
        else:
            st.info(f"Nessun file: {fx_path}")

    # Odds
    with tabs[1]:
        o_path = data_dir / "odds" / "odds_latest.json"
        st.subheader("Odds latest")
        if o_path.exists():
            odds = _load_json(o_path) or {}
            st.json(odds)
        else:
            st.info(f"Nessun file: {o_path}")

    # Predictions
    with tabs[2]:
        p_path = data_dir / "predictions" / "latest_predictions.json"
        st.subheader("Predictions latest")
        if p_path.exists():
            preds = _load_json(p_path) or {}
            st.json(preds)
            # highlight valori
            entries = preds.get("predictions") or []
            if isinstance(entries, list) and entries:
                rows: List[Dict[str, Any]] = []
                for e in entries:
                    if not isinstance(e, dict):
                        continue
                    rid = e.get("fixture_id")
                    prob = e.get("prob_adjusted") or e.get("prob") or {}
                    v = e.get("value", {})
                    side = v.get("best_side")
                    edge = v.get("value_edge")
                    rows.append(
                        {
                            "fixture_id": rid,
                            "best_side": side,
                            "value_edge": edge,
                            "p_home": (prob or {}).get("home_win"),
                            "p_draw": (prob or {}).get("draw"),
                            "p_away": (prob or {}).get("away_win"),
                        }
                    )
                st.write("Value highlights")
                st.dataframe(rows, use_container_width=True)
        else:
            st.info(f"Nessun file: {p_path}")

    # ROI
    with tabs[3]:
        r_path = data_dir / "roi" / "roi_metrics.json"
        st.subheader("ROI metrics")
        if r_path.exists():
            roi = _load_json(r_path) or {}
            st.json(roi)
        else:
            st.info(f"Nessun file: {r_path}")


if __name__ == "__main__":
    main()
