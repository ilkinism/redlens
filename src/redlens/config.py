"""Settings, read from a file and then the environment."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"


@dataclass(frozen=True)
class Config:
    host: str = "127.0.0.1"
    port: int = 3300
    max_document_bytes: int = 20_971_520
    max_paragraphs: int = 20_000
    max_changes: int = 2_000


def _coerce(raw: dict) -> dict:
    fields = {"host": str, "port": int, "max_document_bytes": int,
              "max_paragraphs": int, "max_changes": int}
    out = {}
    for key, cast in fields.items():
        if raw.get(key) is not None:
            try:
                out[key] = cast(raw[key])
            except (TypeError, ValueError):
                continue
    return out


def load_config(path: Path | str | None = None) -> Config:
    source = Path(path) if path else DEFAULT_CONFIG_PATH
    values = {}
    if source.exists():
        try:
            values = _coerce(json.loads(source.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            values = {}
    env = {"host": os.environ.get("REDLENS_HOST"),
           "port": os.environ.get("REDLENS_PORT")}
    values.update(_coerce({k: v for k, v in env.items() if v}))
    return Config(**values)
