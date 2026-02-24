"""Logging configuration using loguru.

Usage::

    from kactus_common.logging import configure_logging
    configure_logging(level="INFO", log_file="app.log")
"""

import sys

from loguru import logger


def configure_logging(
    level: str = "INFO",
    log_file: str | None = "app.log",
    log_format: str = "<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}",
) -> None:
    """Configure loguru with stdout and optional file logging.

    Args:
        level: Minimum log level for stdout (e.g. ``"DEBUG"``, ``"INFO"``).
        log_file: Path for file logging. ``None`` disables file output.
        log_format: Format string for stdout output.
    """
    logger.remove()

    logger.add(
        sys.stdout,
        format=log_format,
        colorize=True,
        level=level,
    )

    if log_file:
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
            rotation="10 MB",
            retention="7 days",
            compression="zip",
            level="DEBUG",
        )
