import logging
import structlog
import sys
from app.core.config import settings
from app.core.log_publisher import RedisLogPublisher


def setup_logging():
    # Set the logging level based on the environment
    log_level = logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG

    # Standard library logging configuration
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Structlog configuration based on environment
    if settings.ENVIRONMENT == "production":
        # JSON formatter for production
        processors = [
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.dict_tracebacks,
            RedisLogPublisher(),
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Colored console output for development
        processors = [
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            RedisLogPublisher(),
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
