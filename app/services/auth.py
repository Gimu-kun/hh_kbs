"""Đăng nhập admin bằng mật khẩu băm SHA-256. Token chỉ sống trong bộ nhớ tiến trình."""

from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path

from app.services.errors import KnowledgeError

_admins: dict[str, dict] = {}
_tokens: dict[str, str] = {}


def configure(data_dir: Path) -> None:
    global _admins
    path = Path(data_dir) / "admins.json"
    _admins = {}
    if not path.exists():
        return
    for item in json.loads(path.read_text(encoding="utf-8")).get("items") or []:
        _admins[item["username"]] = item


def login(username: str, password: str) -> dict:
    record = _admins.get(str(username or "").strip())
    digest = hashlib.sha256(str(password or "").encode("utf-8")).hexdigest()
    if record is None or record.get("password_sha256") != digest or record.get("role") != "admin":
        raise KnowledgeError("Sai tài khoản hoặc mật khẩu admin.", 401)
    token = secrets.token_hex(16)
    _tokens[token] = record["username"]
    return {"token": token, "token_type": "bearer", "username": record["username"], "role": "admin"}


def user_for_token(token: str | None) -> str | None:
    if not token:
        return None
    return _tokens.get(token)
