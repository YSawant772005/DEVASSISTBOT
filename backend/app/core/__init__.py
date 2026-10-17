"""Core helpers: settings, errors, logging."""

from __future__ import annotations

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once with a compact, secret-free format."""
    root = logging.getLogger()
    if getattr(root, "_devassist_configured", False):
        root.setLevel(level)
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root.handlers = [handler]
    root.setLevel(level)
    root._devassist_configured = True  # type: ignore[attr-defined]

    # Keep noisy third-party loggers reasonably quiet.
    for name in ("httpx", "httpcore", "sentence_transformers", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)
