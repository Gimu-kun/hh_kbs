"""Phân tích công thức hóa học và phương trình."""

from __future__ import annotations

import re

from app.core.numbers import format_number


class FormulaError(ValueError):
    pass


class EquationError(ValueError):
    pass


_ARROW = re.compile(r"\s*(?:→|->|=>|=|—>|‒>|⟶)\s*")
_TOKEN = re.compile(r"^(\d+)?\s*([A-Z(][A-Za-z0-9()\[\]]*?)$")


def parse_formula(formula: str) -> dict[str, int]:
    """Tách công thức thành số nguyên tử từng nguyên tố. Hỗ trợ ngoặc (), []."""
    text = formula.strip().replace("·", ".").replace("•", ".")
    if not text:
        raise FormulaError("Công thức rỗng.")
    if "." in text:
        parts = text.split(".")
        total: dict[str, int] = {}
        for part in parts:
            hydrate = re.fullmatch(r"(\d+)?([A-Za-z0-9()\[\]]+)", part)
            if not hydrate:
                raise FormulaError(f"Không phân tích được công thức '{formula}'.")
            factor = int(hydrate.group(1) or "1")
            _merge(total, _parse_unit(hydrate.group(2)), factor)
        return total
    return _parse_unit(text)


def _parse_unit(text: str) -> dict[str, int]:
    counts, index = _parse_group(text, 0)
    if index != len(text):
        raise FormulaError(f"Không phân tích được công thức '{text}'.")
    if not counts:
        raise FormulaError(f"Công thức '{text}' không chứa nguyên tố.")
    return counts


def _parse_group(text: str, index: int) -> tuple[dict[str, int], int]:
    counts: dict[str, int] = {}
    while index < len(text) and text[index] not in ")]":
        char = text[index]
        if char in "([":
            closing = ")" if char == "(" else "]"
            inner, index = _parse_group(text, index + 1)
            if index >= len(text) or text[index] != closing:
                raise FormulaError(f"Công thức '{text}' thiếu ngoặc đóng.")
            index += 1
            number, index = _read_number(text, index)
            _merge(counts, inner, number)
            continue
        if not char.isupper():
            raise FormulaError(f"Không phân tích được công thức '{text}'.")
        element = char
        index += 1
        if index < len(text) and text[index].islower():
            element += text[index]
            index += 1
        number, index = _read_number(text, index)
        counts[element] = counts.get(element, 0) + number
    return counts, index


def _read_number(text: str, index: int) -> tuple[int, int]:
    if index >= len(text) or not text[index].isdigit():
        return 1, index
    start = index
    while index < len(text) and text[index].isdigit():
        index += 1
    return int(text[start:index]), index


def _merge(target: dict[str, int], source: dict[str, int], factor: int) -> None:
    for element, count in source.items():
        target[element] = target.get(element, 0) + count * factor


def composition_text(composition: dict[str, int]) -> str:
    return ", ".join(f"{element}: {count}" for element, count in composition.items())


def clean_species(token: str) -> str:
    """Bỏ chú thích trạng thái, mũi tên kết tủa và hệ số đứng trước."""
    text = token.strip()
    text = text.replace("↓", "").replace("↑", "").replace(" ", "")
    text = re.sub(r"\((?:r|k|l|dd|s|g|aq|ran|long|khi|dungdich)\)$", "", text, flags=re.IGNORECASE)
    return text


def split_term(term: str) -> tuple[int, str]:
    text = term.strip()
    text = text.replace("↓", "").replace("↑", "")
    text = re.sub(
        r"\((?:r|k|l|dd|s|g|aq|rắn|lỏng|khí|dd|đặc|loãng)\)\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    match = re.fullmatch(r"(\d+)\s*([A-Z(].+)", text)
    if match:
        return int(match.group(1)), clean_species(match.group(2))
    return 1, clean_species(text)


def parse_equation(equation: str) -> tuple[list[str], list[str]]:
    """Tách phương trình thành danh sách công thức chất tham gia và sản phẩm.

    Hệ số viết sẵn bị bỏ qua vì bộ cân bằng sẽ tính lại.
    """
    compact = equation.strip()
    if not compact:
        raise EquationError("Phương trình rỗng.")
    parts = _ARROW.split(compact, maxsplit=1)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise EquationError("Phương trình cần có dạng: chất tham gia → sản phẩm.")
    reactants = _split_side(parts[0])
    products = _split_side(parts[1])
    if not reactants or not products:
        raise EquationError("Mỗi vế của phương trình cần ít nhất một chất.")
    return reactants, products


def _split_side(side: str) -> list[str]:
    formulas = []
    for raw in side.split("+"):
        if not raw.strip():
            continue
        _coefficient, formula = split_term(raw)
        if not formula:
            raise EquationError(f"Không đọc được chất trong '{raw.strip()}'.")
        parse_formula(formula)
        formulas.append(formula)
    return formulas


def format_side(formulas: list[str], coefficients: list[int]) -> str:
    parts = []
    for formula, coefficient in zip(formulas, coefficients):
        if coefficient == 1:
            parts.append(formula)
        else:
            parts.append(f"{format_number(coefficient)}{formula}")
    return " + ".join(parts)


def format_equation(
    reactants: list[str],
    products: list[str],
    coefficients: list[int],
    condition_symbol: str | None = None,
) -> str:
    count = len(reactants)
    left = format_side(reactants, coefficients[:count])
    right = format_side(products, coefficients[count:])
    if condition_symbol:
        arrow = f"--{condition_symbol}→"
    else:
        arrow = "→"
    return f"{left} {arrow} {right}"
