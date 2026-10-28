"""
logger.py — Custom Logger for Playwright Scraper

Features:
  - Colored console output by log level
  - Optional file logging with automatic log rotation
  - Per-site/module named loggers
  - Timestamped entries
  - Simple setup: just call get_logger(__name__)

Usage:
    from logger import get_logger

    log = get_logger(__name__)
    log.info("Starting scrape")
    log.success("Scraped 10 items")   # custom level
    log.warning("Retrying...")
    log.error("Failed to load page")
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# ── ANSI color codes ──────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"

COLORS = {
    "DEBUG":    "\033[36m",    # Cyan
    "INFO":     "\033[34m",    # Blue
    "SUCCESS":  "\033[32m",    # Green
    "WARNING":  "\033[33m",    # Yellow
    "ERROR":    "\033[31m",    # Red
    "CRITICAL": "\033[41m",    # Red background
}

ICONS = {
    "DEBUG":    "🔧",
    "INFO":     "ℹ️ ",
    "SUCCESS":  "✅",
    "WARNING":  "⚠️ ",
    "ERROR":    "❌",
    "CRITICAL": "🔥",
}

# ── Custom SUCCESS level ───────────────────────────────────────────────────────

SUCCESS_LEVEL = 25  # between INFO (20) and WARNING (30)
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")


def _success(self, message, *args, **kwargs):
    if self.isEnabledFor(SUCCESS_LEVEL):
        self._log(SUCCESS_LEVEL, message, args, **kwargs)

logging.Logger.success = _success  # type: ignore


# ── Colored console formatter ──────────────────────────────────────────────────

class ColorFormatter(logging.Formatter):
    def __init__(self, show_logger_name: bool = True):
        super().__init__()
        self.show_logger_name = show_logger_name

    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname
        color = COLORS.get(level, RESET)
        icon  = ICONS.get(level, "  ")

        # Shorten logger name to last component (e.g. "sites.quotes" → "quotes")
        name = record.name.split(".")[-1] if self.show_logger_name else ""
        name_part = f"{BOLD}[{name}]{RESET} " if name else ""

        timestamp = self.formatTime(record, datefmt="%H:%M:%S")

        level_tag = f"{color}{BOLD}{level:<8}{RESET}"
        message   = record.getMessage()

        # Append exception info if present
        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)

        return f"{BOLD}{timestamp}{RESET}  {icon}  {level_tag}  {name_part}{message}"


# ── Plain file formatter (no ANSI codes) ───────────────────────────────────────

class FileFormatter(logging.Formatter):
    FMT = "%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s"
    DATEFMT = "%Y-%m-%d %H:%M:%S"

    def __init__(self):
        super().__init__(fmt=self.FMT, datefmt=self.DATEFMT)


# ── Logger factory ─────────────────────────────────────────────────────────────

def get_logger(
    name: str,
    level: int = logging.DEBUG,
    log_file: Optional[str] = None,
    max_bytes: int = 5 * 1024 * 1024,   # 5 MB per file
    backup_count: int = 3,               # keep 3 rotated files
    show_logger_name: bool = True,
) -> logging.Logger:
    """
    Create (or retrieve) a named logger with colored console output
    and optional rotating file logging.

    Args:
        name:             Logger name, use __name__ for automatic naming.
        level:            Minimum log level (default: DEBUG).
        log_file:         Path to log file. If None, file logging is disabled.
        max_bytes:        Max size per log file before rotation (default: 5MB).
        backup_count:     Number of rotated files to keep (default: 3).
        show_logger_name: Show module name in console output (default: True).

    Returns:
        A configured logging.Logger instance with a .success() method.

    Examples:
        log = get_logger(__name__)
        log = get_logger("quotes", log_file="logs/scraper.log")
        log = get_logger(__name__, level=logging.WARNING)
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False  # don't bubble up to root logger

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(ColorFormatter(show_logger_name=show_logger_name))
    logger.addHandler(console)

    # File handler (optional)
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(FileFormatter())
        logger.addHandler(file_handler)

    return logger


# ── Module-level default logger ────────────────────────────────────────────────

# A ready-to-use logger for quick imports:
#   from logger import log
#   log.info("hello")
log = get_logger("scraper")