"""Project logging. Rich on the console, plain text in logs/medha.log."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

import config

_CONFIGURED = False


def setup_logging(level: str = "INFO") -> logging.Logger:
    global _CONFIGURED
    root = logging.getLogger("medha")
    if _CONFIGURED:
        return root

    config.ensure_dirs()
    root.setLevel(level.upper())
    root.propagate = False

    try:
        from rich.logging import RichHandler

        console: logging.Handler = RichHandler(rich_tracebacks=True, markup=True)
        console.setFormatter(logging.Formatter("%(message)s", datefmt="%H:%M:%S"))
    except Exception:  # pragma: no cover - rich is a base dependency
        console = logging.StreamHandler()
        console.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
        )

    file_handler = RotatingFileHandler(
        config.LOG_DIR / "medha.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    )

    root.addHandler(console)
    root.addHandler(file_handler)
    _CONFIGURED = True
    return root


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name if name.startswith("medha") else f"medha.{name}")
