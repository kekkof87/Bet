from core.logging import get_logger


def test_get_logger_idempotent() -> None:
    logger1 = get_logger("test.logger")
    handlers_before = list(logger1.handlers)
    logger2 = get_logger("test.logger")
    assert logger1 is logger2
    assert len(logger1.handlers) == len(handlers_before)
