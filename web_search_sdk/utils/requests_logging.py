"""DEPRECATED: Requests logging functionality has been merged into utils.logging.

This module is kept for backward compatibility only. Import from utils.logging instead.
"""

from __future__ import annotations

import warnings

from .logging import get_logger

warnings.warn(
    "requests_logging module is deprecated and will be removed in a future version. "
    "Import from utils.logging instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["get_logger"]
