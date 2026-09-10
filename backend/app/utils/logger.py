"""Centralized logging configuration.

Course: BBAT104 - Fundamentals of TQM
Quality Goal: Q05 - Reduce Response Time
"""

import logging
import sys


def setup_logger(name: str = "hms_app", level: int = logging.INFO) -> logging.Logger:
    """Create and configure a structured console logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
    return logger


logger = setup_logger()
