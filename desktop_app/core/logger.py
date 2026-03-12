"""
desktop_app/core/logger.py — Application-wide logging service.
Uses loguru for structured logging. Emits Qt signals for the UI log viewer.
"""
import os
import sys
from datetime import datetime
from PySide6.QtCore import QObject, Signal
from loguru import logger as _loguru


# Output log directory
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output", "logs")


class AppLogger(QObject):
    """
    Wraps loguru. Emits log_message(level, message) Qt signal so the
    Logs page can display live entries without polling files.
    """
    log_message = Signal(str, str)  # (level, message)

    def __init__(self):
        super().__init__()
        os.makedirs(LOG_DIR, exist_ok=True)

        # Remove default loguru sink
        _loguru.remove()

        # File sink with rotation
        log_file = os.path.join(LOG_DIR, "app_{time:YYYY-MM-DD}.log")
        _loguru.add(log_file, rotation="1 day", retention="7 days",
                    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message}",
                    level="DEBUG")

        # Stdout sink
        _loguru.add(sys.stdout,
                    format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
                    level="INFO")

        # Qt signal sink
        _loguru.add(self._qt_sink, level="DEBUG", format="{level}|{message}")

    def _qt_sink(self, message):
        record = message.record
        self.log_message.emit(record["level"].name, record["message"])

    def debug(self, msg: str):
        _loguru.debug(msg)

    def info(self, msg: str):
        _loguru.info(msg)

    def warning(self, msg: str):
        _loguru.warning(msg)

    def error(self, msg: str):
        _loguru.error(msg)

    def critical(self, msg: str):
        _loguru.critical(msg)

    def get_log_dir(self) -> str:
        return LOG_DIR
