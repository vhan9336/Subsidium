"""Reads config.toml into plain dicts."""
import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load(path=None) -> dict:
    with open(path or ROOT / "config.toml", "rb") as f:
        return tomllib.load(f)
