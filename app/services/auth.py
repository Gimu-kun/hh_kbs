"""Đăng nhập admin. Mật khẩu mặc định lấy từ biến môi trường, băm bằng PBKDF2 khi đổi."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from pathlib import Path

from app.services.errors import KnowledgeError

_admins: dict[str, dict] = {}
_tokens: dict[str, dict] = {}
_path: Path | None = None
_TOKEN_TTL = 8 * 60 * 60
_ITERATIONS = 200_000


def configure(data_dir: Path) -> None:
    global _admins, _path
    _path = Path(data_dir) / "admins.json"
    _admins = {}
    _tokens.clear()
    if not _path.exists():
        return
    for item in json.loads(_path.read_text(encoding="utf-8")).get("items") or []:
        _admins[item["username"]] = item


def _verify_stored(record: dict, password: str) -> bool:
    salt = str(record.get("password_salt") or "")
    digest = str(record.get("password_hash") or "")
    iterations = int(record.get("password_iterations") or _ITERATIONS)
    if not salt or not digest:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations).hex()
    return secrets.compare_digest(check, digest)


def _check_password(record: dict, password: str) -> None:
    if record.get("password_hash"):
        if not _verify_stored(record, password):
            raise KnowledgeError("Sai tài khoản hoặc mật khẩu admin.", 401)
        return
    expected = os.environ.get("KBS_ADMIN_PASSWORD") or ""
    if not expected:
        raise KnowledgeError("Chưa cấu hình biến môi trường KBS_ADMIN_PASSWORD.", 503)
    if not secrets.compare_digest(str(password or ""), expected):
        raise KnowledgeError("Sai tài khoản hoặc mật khẩu admin.", 401)


def login(username: str, password: str) -> dict:
    record = _admins.get(str(username or "").strip())
    if record is None or record.get("role") != "admin":
        raise KnowledgeError("Sai tài khoản hoặc mật khẩu admin.", 401)
    _check_password(record, str(password or ""))
    must_change = bool(record.get("must_change_password", not record.get("password_hash")))
    token = secrets.token_hex(16)
    _tokens[token] = {
        "username": record["username"],
        "exp": time.time() + _TOKEN_TTL,
        "scope": "password_change" if must_change else "full",
    }
    return {
        "token": token,
        "token_type": "bearer",
        "username": record["username"],
        "role": "admin",
        "must_change_password": must_change,
        "expires_in": _TOKEN_TTL,
    }


def user_for_token(token: str | None) -> dict | None:
    if not token:
        return None
    record = _tokens.get(token)
    if record is None:
        return None
    if record["exp"] <= time.time():
        _tokens.pop(token, None)
        return None
    return record


def logout(token: str | None) -> dict:
    if token:
        _tokens.pop(token, None)
    return {"logged_out": True}


def change_password(username: str, current_password: str, new_password: str) -> dict:
    record = _admins.get(username)
    if record is None:
        raise KnowledgeError("Sai tài khoản hoặc mật khẩu admin.", 401)
    _check_password(record, current_password)
    new_password = str(new_password or "")
    if len(new_password) < 8:
        raise KnowledgeError("Mật khẩu mới phải có ít nhất 8 ký tự.")
    if record.get("password_hash") and _verify_stored(record, new_password):
        raise KnowledgeError("Mật khẩu mới phải khác mật khẩu hiện tại.")
    salt = secrets.token_hex(16)
    record["password_hash"] = hashlib.pbkdf2_hmac(
        "sha256", new_password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS
    ).hex()
    record["password_salt"] = salt
    record["password_iterations"] = _ITERATIONS
    record["must_change_password"] = False
    record.pop("password_sha256", None)
    record.pop("note", None)
    _save()
    return {"username": username, "must_change_password": False}


def _save() -> None:
    if _path is None:
        raise KnowledgeError("Chưa cấu hình tệp quản trị.")
    _path.parent.mkdir(parents=True, exist_ok=True)
    _path.write_text(
        json.dumps({"items": list(_admins.values())}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
