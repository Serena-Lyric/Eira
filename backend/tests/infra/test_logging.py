import json
import structlog
from app.core.logging import configure_logging


def test_log_emits_json(capsys):
    configure_logging()
    log = structlog.get_logger()
    log.info("hello", request_id="r1", user_id="u1", latency_ms=42)
    captured = capsys.readouterr().out.strip()
    payload = json.loads(captured)
    assert payload["event"] == "hello"
    assert payload["request_id"] == "r1"
    assert payload["user_id"] == "u1"
    assert payload["latency_ms"] == 42
    assert "ts" in payload and "level" in payload
