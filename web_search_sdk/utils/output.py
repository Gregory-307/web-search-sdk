"""Lightweight output helpers (JSON/CSV). Designed for idempotent batch scripts.

Usage
-----
>>> from web_search_sdk.utils.output import to_json, to_csv
>>> to_json(data, "results.json")
>>> to_csv([{"a":1,"b":2}], "results.csv")
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

__all__ = [
    "to_json",
    "to_csv",
]


def _ensure_parent(path: Path) -> None:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def to_json(data: Any, file_path: str | Path, append: bool = False) -> None:
    """Write *data* to *file_path* as JSON.

    If *append* is True and the file already exists, the existing content is
    treated as a JSON list; *data* is appended (list extended) and written back.
    Otherwise the file is overwritten.
    """
    path = Path(file_path)
    _ensure_parent(path)

    if append and path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = []
        if not isinstance(existing, list):
            existing = [existing]
        existing.append(data)
        to_write = existing
    else:
        to_write = data

    path.write_text(json.dumps(to_write, ensure_ascii=False, indent=2), encoding="utf-8")


def to_csv(rows: list[dict[str, Any]], file_path: str | Path, append: bool = False) -> None:
    """Write list-of-dicts *rows* to CSV at *file_path*.

    Fieldnames are inferred from the first row. If *append* is True and the file
    exists, rows are appended without rewriting the header.
    """
    if not rows:
        return

    path = Path(file_path)
    _ensure_parent(path)

    mode = "a" if append and path.exists() else "w"
    write_header = not path.exists() or mode == "w"

    fieldnames = list(rows[0].keys())
    with path.open(mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)
