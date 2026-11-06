"""Ghép mẫu câu đã lưu thành lời giải tiếng Việt."""

from __future__ import annotations

import json
import re
from fractions import Fraction

from cstt import kb as kb_paths

_PLACEHOLDER = re.compile(r"\{([a-zA-Z0-9_]+)\}")
_TEMPLATES: dict | None = None

_DON_VI = {
    "m": "gam",
    "g": "gam",
    "n": "mol",
    "mol": "mol",
    "V": "lít",
    "L": "lít",
    "CM": "mol/lít",
    "mol/L": "mol/lít",
    "Vdd": "lít",
    "M": "gam/mol",
    "g/mol": "gam/mol",
}


def so_sgk(value) -> str:
    number = value if isinstance(value, Fraction) else Fraction(str(value))
    if number.denominator == 1:
        text = str(number.numerator)
    else:
        text = f"{float(number):.6f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def don_vi_chu(unit: str) -> str:
    return _DON_VI[unit]


def ten_dai_luong(quantity: str, formula: str) -> str:
    names = {
        "m": f"khối lượng của {formula}",
        "n": f"số mol của {formula}",
        "V": f"thể tích khí {formula}",
        "CM": f"nồng độ mol của {formula}",
        "Vdd": f"thể tích dung dịch {formula}",
        "M": f"khối lượng mol của {formula}",
    }
    return names[quantity]


def viet_thuong(text: str) -> str:
    if not text:
        return text
    return text[:1].lower() + text[1:]


def liet_ke(items: list[str]) -> str:
    if not items:
        return "không có chất nào khác"
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " và " + items[-1]


def giai_thich_tu_nhien(text: str, ten_luat: str) -> str:
    """Dùng lời luật khi câu giải thích còn mã độ tan hoặc mã quy tắc."""
    if re.search(r"SOL_|khong_tan|it_tan", text):
        text = ten_luat
    return viet_thuong(re.sub(r"\s+", " ", text).strip().rstrip("."))


def load_templates() -> dict:
    global _TEMPLATES
    if _TEMPLATES is None:
        path = kb_paths.RULES / "templates.json"
        with path.open(encoding="utf-8") as handle:
            _TEMPLATES = json.load(handle)
    return _TEMPLATES


def reset_templates() -> None:
    global _TEMPLATES
    _TEMPLATES = None


def trinh_bay(problem: dict, result: dict) -> str:
    book = load_templates()
    clauses = []
    for step in result.get("vet") or []:
        mau = step.get("mau")
        if not mau:
            continue
        clauses.append(_fill(book["mau"][mau], step.get("tham_so") or {}, mau))
    case = result.get("_truong_hop")
    ket_id = book["truong_hop"].get(case or "")
    if ket_id:
        clauses.append(_fill(book["mau"][ket_id], _ket_params(problem, result), ket_id))
    return _join(book["noi"], clauses)


def _ket_params(problem: dict, result: dict) -> dict:
    extra = dict(result.get("_tham_so") or {})
    tim = problem.get("tim") or {}
    chat_dich = problem.get("chat_dich") or tim.get("chat", "")
    params = {
        "phuong_trinh": result.get("phuong_trinh", ""),
        "so_do": str(problem.get("phan_ung", "")).replace("->", "→").replace("=", "→"),
        "chat_dau": problem.get("chat_dau", ""),
        "chat_dich": chat_dich,
        "chat": problem.get("chat_dau") or chat_dich,
        "so_buoc": result.get("so_buoc", ""),
        "chuoi": "; ".join(result.get("chuoi") or []),
        "pham_vi": "",
        "do_sau": "",
        "ten_dai_luong": "",
        "ket_qua": str(result.get("ket_qua", "")).replace(".", ","),
        "don_vi_chu": _DON_VI.get(result.get("don_vi", ""), ""),
        "chat_tham_gia": ", ".join(problem.get("chat_tham_gia") or []),
        "ung_vien": "; ".join(result.get("phuong_trinh_ung_vien") or []),
        "ly_do": str(result.get("thong_bao", "")).rstrip("."),
        "trang_thai": "",
    }
    if tim.get("dai_luong") and tim.get("chat"):
        params["ten_dai_luong"] = ten_dai_luong(tim["dai_luong"], tim["chat"])
    params.update(extra)
    return params


def _fill(text: str, params: dict, mau: str) -> str:
    missing = [name for name in _PLACEHOLDER.findall(text) if name not in params]
    if missing:
        names = ", ".join(missing)
        raise KeyError(f"Mẫu {mau} thiếu {names}.")

    def replace(match: re.Match) -> str:
        return str(params[match.group(1)])

    return _PLACEHOLDER.sub(replace, text)


def _join(connectors: dict, clauses: list[str]) -> str:
    if not clauses:
        return ""
    if len(clauses) == 1:
        return connectors["ket"].format(cau=clauses[0])
    lines = [connectors["dau"].format(cau=clauses[0])]
    lines.extend(connectors["tiep"].format(cau=clause) for clause in clauses[1:-1])
    lines.append(connectors["ket"].format(cau=clauses[-1]))
    return "\n".join(lines)
