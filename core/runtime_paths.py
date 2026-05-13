"""Runtime path helpers for desktop and server deployments."""
import os
from pathlib import Path


def get_data_dir() -> Path:
    configured = os.environ.get("FRONTLINES_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.cwd().resolve()


def ensure_data_dir() -> Path:
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_db_path() -> str:
    return str(ensure_data_dir() / "skutto.db")


def get_data_path(name: str) -> str:
    path = ensure_data_dir() / name
    path.mkdir(parents=True, exist_ok=True)
    return str(path)
