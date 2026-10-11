"""Loads config.toml into plain dicts (stdlib tomllib, no extra dependency)."""
from __future__ import annotations

import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load(path: str | pathlib.Path | None = None) -> dict:
    p = pathlib.Path(path) if path else ROOT / "config.toml"
    with open(p, "rb") as f:
        return tomllib.load(f)
