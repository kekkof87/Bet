# ... (tutto il contenuto precedente invariato FINO alla dataclass Settings)

@dataclass
class Settings:
    # (campi già esistenti)
    enable_value_detection: bool
    value_min_edge: float
    value_include_adjusted: bool

    # Value alerts (NEW)
    enable_value_alerts: bool
    value_alerts_dir: str

    @classmethod
    def from_env(cls) -> "Settings":
        # ... parsing precedente invariato ...
        enable_value_detection = _parse_bool(os.getenv("ENABLE_VALUE_DETECTION"), False)
        value_min_edge = _float("VALUE_MIN_EDGE", 0.05)
        value_include_adjusted = _parse_bool(os.getenv("VALUE_INCLUDE_ADJUSTED"), True)

        # NEW
        enable_value_alerts = _parse_bool(os.getenv("ENABLE_VALUE_ALERTS"), False)
        value_alerts_dir = os.getenv("VALUE_ALERTS_DIR", "value_alerts")

        return cls(
            # ... tutti i parametri precedenti ...
            enable_value_detection=enable_value_detection,
            value_min_edge=value_min_edge,
            value_include_adjusted=value_include_adjusted,
            enable_value_alerts=enable_value_alerts,
            value_alerts_dir=value_alerts_dir,
        )
