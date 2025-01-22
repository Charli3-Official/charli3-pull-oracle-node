"""logging module config."""

import logging

LEVEL_COLORS = {
    0: "\033[0m",  # No Set
    1: "\033[36m",  # Debug
    2: "\033[34m",  # Info
    3: "\033[33m",  # Warning
    4: "\033[31m",  # Error
    5: "\033[1;31m",  # Critical
}

LOG_FORMAT = (
    "%(level_color)s[%(name)s:%(levelname)s]%(end_color)s [%(asctime)s] %(message)s"
)


def get_log_config(ini_updater):
    """get log_config."""
    log_level = getattr(logging, ini_updater["verbosity"], logging.INFO)

    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": LOG_FORMAT,
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                "level": log_level,
                "level_colors": LEVEL_COLORS,
            },
            "json": {
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
            },
        },
        "handlers": {
            "standard": {"class": "logging.StreamHandler", "formatter": "standard"}
        },
        "loggers": {"": {"handlers": ["standard"], "level": log_level}},
    }

    return log_config
