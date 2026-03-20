"""
logger.py — Centralized logging setup.

get_logger(name, config=None) returns a logger that writes to both
console and a rotating file under output/logs/.
"""

import logging
import logging.handlers
import os
from pathlib import Path


_INITIALIZED: set = set()
_LOG_DIR: Path = Path("output/logs")
_LOG_LEVEL: int = logging.INFO


def _ensure_log_dir(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)


def configure_logging(config=None) -> None:
    """
    Call once at startup (optional) to configure global log level and directory
    from the loaded Config object.
    """
    global _LOG_DIR, _LOG_LEVEL
    if config is not None:
        try:
            _LOG_DIR = Path(config.logging.log_dir)
        except AttributeError:
            pass
        try:
            level_str = str(config.logging.level).upper()
            _LOG_LEVEL = getattr(logging, level_str, logging.INFO)
        except AttributeError:
            pass
    _ensure_log_dir(_LOG_DIR)


def get_logger(name: str, config=None) -> logging.Logger:
    """
    Return a logger named *name*.

    On first call for a given name the logger is configured with:
    - StreamHandler (console) at the global log level
    - RotatingFileHandler writing to output/logs/<name>.log

    Subsequent calls return the cached logger.
    """
    global _LOG_DIR, _LOG_LEVEL

    logger = logging.getLogger(name)

    if name in _INITIALIZED:
        return logger

    # Optionally reconfigure from config
    if config is not None:
        configure_logging(config)

    logger.setLevel(_LOG_LEVEL)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
               for h in logger.handlers):
        ch = logging.StreamHandler()
        ch.setLevel(_LOG_LEVEL)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    # File handler
    _ensure_log_dir(_LOG_DIR)
    log_file = _LOG_DIR / f"{name.replace('.', '_')}.log"
    try:
        fh = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=3,
            encoding="utf-8",
        )
        fh.setLevel(_LOG_LEVEL)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except OSError as exc:
        logger.warning("Could not open log file %s: %s", log_file, exc)

    logger.propagate = False
    _INITIALIZED.add(name)
    return logger
