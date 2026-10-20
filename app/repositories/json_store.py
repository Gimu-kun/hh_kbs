"""Đọc và ghi từng tập tri thức trong một file JSON."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from pathlib import Path


class JsonStore:
    def __init__(self, path: Path, id_field: str):
        self.path = path
        self.id_field = id_field
        self._lock = threading.RLock()
        self._items: dict[str, dict] = {}
        self.load()

    def load(self) -> None:
        with self._lock:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            items = payload["items"] if isinstance(payload, dict) else payload
            self._items = {str(item[self.id_field]): item for item in items}

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = {"items": list(self._items.values())}
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def list(self) -> list[dict]:
        with self._lock:
            return [deepcopy(item) for item in self._items.values()]

    def get(self, item_id: str) -> dict | None:
        with self._lock:
            item = self._items.get(str(item_id))
            return deepcopy(item) if item else None

    def exists(self, item_id: str) -> bool:
        with self._lock:
            return str(item_id) in self._items

    def create(self, item: dict) -> dict:
        with self._lock:
            item_id = str(item[self.id_field])
            if item_id in self._items:
                raise KeyError(item_id)
            self._items[item_id] = item
            self._flush()
            return deepcopy(item)

    def replace(self, item_id: str, item: dict) -> dict | None:
        with self._lock:
            key = str(item_id)
            if key not in self._items:
                return None
            self._items.pop(key)
            self._items[str(item[self.id_field])] = item
            self._flush()
            return deepcopy(item)

    def delete(self, item_id: str) -> dict | None:
        with self._lock:
            item = self._items.pop(str(item_id), None)
            if item is None:
                return None
            self._flush()
            return deepcopy(item)
