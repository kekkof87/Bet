from typing import Any, Dict
import pandas as pd

def add_status_badge(df: pd.DataFrame, col: str = "status") -> pd.DataFrame:
    if col not in df.columns:
        return df
    def badge(s: Any) -> str:
        s_up = str(s).upper()
        if s_up in {"1H","HT","2H"}:
            return "🟢 LIVE"
        if s_up == "NS":
            return "🕒"
        if s_up == "FT":
            return "🏁"
        if s_up == "PST":
            return "⏸️"
        return ""
    out = df.copy()
    out.insert(0, "state", out[col].apply(badge))
    return out

def edge_color(edge: float) -> str:
    if edge >= 0.1:  # >= 10%
        return "🟢"
    if edge >= 0.05:
        return "🟡"
    if edge >= 0.03:
        return "🟠"
    return "⚪"
