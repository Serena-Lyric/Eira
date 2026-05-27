import logging
import sys
import structlog
from app.core.config import get_settings


def configure_logging() -> None:
    level = getattr(logging, get_settings().app.log_level.upper(), logging.INFO)
    logging.basicConfig(stream=sys.stdout, level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", key="ts"),
            structlog.processors.add_log_level,
            structlog.processors.EventRenamer("event"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
