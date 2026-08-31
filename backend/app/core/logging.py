import logging
import sys
from app.config import settings


def setup_logging() -> logging.Logger:
    """
    Configures structured logging for the application.
    Applies the configured log level and format to root and application loggers.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    log_format = (
        "[%(asctime)s] [%(levelname)-8s] [%(name)s]: %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Set specific log level for application package
    app_logger = logging.getLogger("app")
    app_logger.setLevel(log_level)

    # Suppress overly verbose third-party loggers if needed
    logging.getLogger("uvicorn.access").setLevel(log_level)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.APP_ENV == "development" and log_level == logging.DEBUG else logging.WARNING
    )

    return app_logger
