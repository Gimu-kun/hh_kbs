"""Cấu hình đường dẫn dữ liệu."""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    override = os.environ.get("KBS_DATA_DIR")
    if override:
        return Path(override)
    return ROOT_DIR / "data"
