import logging

try:
    from rich.logging import RichHandler  # type: ignore
    _RICH = True
except Exception:
    _RICH = False

from core.config import get_settings

_CONFIGURED = False


def _configure():
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = "INFO"
    try:
        level = get_settings().log_level
    except Exception:
        pass

    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))

    if root.handlers:
        _CONFIGURED = True
        return

    if _RICH:
        handler = RichHandler(rich_tracebacks=True, show_time=True)
        fmt = "[%(name)s] %(levelname)s: %(message)s"
        handler.setFormatter(logging.Formatter(fmt))
        root.addHandler(handler)
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            "%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(handler)

    _CONFIGURED = True


def get_logger(name: str):
    _configure()
    return logging.getLogger(name)