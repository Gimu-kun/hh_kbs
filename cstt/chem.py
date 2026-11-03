"""Phân tích công thức, kiểm tra R1 và cân bằng theo bảo toàn nguyên tố."""

from __future__ import annotations

import re
from fractions import Fraction
from functools import reduce
from math import gcd


class ChemError(Exception):
    pass


def parse_composition(formula: str, elements: dict) -> list[dict]:
    """Đọc công thức thành mảng [{element, quantity}] theo thứ tự xuất hiện."""

    def read_count(text: str, index: int) -> tuple[int, int]:
        match = re.match(r"\d+", text[index:])
        if not match:
            return 1, index
        return int(match.group()), index + len(match.group())

    def read_piece(text: str, index: int) -> tuple[dict, int]:
        counts: dict[str, int] = {}
        while index < len(text) and text[index] != ")":
            if text[index] == "(":
                inner, index = read_piece(text, index + 1)
                if index >= len(text) or text[index] != ")":
                    raise ChemError(f"Công thức {formula} thiếu dấu đóng ngoặc.")
                index += 1
                count, index = read_count(text, index)
                for symbol, qty in inner.items():
                    counts[symbol] = counts.get(symbol, 0) + qty * count
                continue
            match = re.match(r"[A-Z][a-z]?", text[index:])
            if not match:
                raise ChemError(f"Không đọc được công thức {formula}.")
            symbol = match.group()
            if symbol not in elements:
                raise ChemError(f"Nguyên tố {symbol} không thuộc phạm vi THCS.")
            index += len(symbol)
            count, index = read_count(text, index)
            counts[symbol] = counts.get(symbol, 0) + count
        return counts, index

    counts, index = read_piece(formula, 0)
    if index != len(formula) or not counts:
        raise ChemError(f"Không đọc được công thức {formula}.")
    return [{"element": symbol, "quantity": qty} for symbol, qty in counts.items()]


def as_map(composition: list[dict]) -> dict[str, int]:
    return {item["element"]: item["quantity"] for item in composition}


def _lcm(a: int, b: int) -> int:
    return abs(a * b) // gcd(a, b) if a and b else 0


def match_anion(text: str, anions: list[dict]) -> tuple[dict, int]:
    if text.startswith("("):
        match = re.fullmatch(r"\(([A-Za-z0-9]+)\)(\d*)", text)
        if not match:
            raise ChemError(f"Không nhận ra nhóm {text}.")
        name, count_text = match.group(1), match.group(2)
        count = int(count_text or "1")
    else:
        name, count = None, None
        for anion in anions:
            prefix = anion["formula"]
            if text.startswith(prefix):
                rest = text[len(prefix) :]
                if rest == "" or rest.isdigit():
                    name = prefix
                    count = int(rest or "1")
                    break
        if name is None:
            raise ChemError(f"Không nhận ra anion trong {text}.")
    found = next((item for item in anions if item["formula"] == name), None)
    if found is None:
        raise ChemError(f"Nhóm {name} không có trong luật R1.")
    return found, count


def split_formula(formula: str, anions: list[dict]) -> dict:
    """Tách cation/anion khi suy diễn. Kết quả không ghi vào dữ liệu chất."""
    if formula.startswith("(NH4)"):
        match = re.fullmatch(r"\(NH4\)(\d*)(.+)", formula)
        if not match:
            raise ChemError(f"Không tách được {formula}.")
        count = int(match.group(1) or "1")
        anion, anion_count = match_anion(match.group(2), anions)
        return {
            "cation": "NH4",
            "cation_count": count,
            "anion": anion,
            "anion_count": anion_count,
        }
    if formula.startswith("NH4"):
        anion, anion_count = match_anion(formula[3:], anions)
        return {
            "cation": "NH4",
            "cation_count": 1,
            "anion": anion,
            "anion_count": anion_count,
        }
    match = re.fullmatch(r"([A-Z][a-z]?)(\d*)(.+)", formula)
    if not match:
        raise ChemError(f"Không tách được {formula}.")
    anion, anion_count = match_anion(match.group(3), anions)
    return {
        "cation": match.group(1),
        "cation_count": int(match.group(2) or "1"),
        "anion": anion,
        "anion_count": anion_count,
    }


def cation_charge(symbol: str, elements: dict) -> int | None:
    if symbol == "NH4":
        return 1
    element = elements.get(symbol)
    if not element or element["type"] != "kim_loai":
        return None
    valences = element["valence"]
    return valences[0] if len(valences) == 1 else None


def oxide_valence(formula: str, composition: dict, elements: dict) -> int | None:
    others = [symbol for symbol in composition if symbol != "O"]
    if len(others) != 1 or "O" not in composition:
        return None
    metal = others[0]
    oxygen_count = composition["O"]
    metal_count = composition[metal]
    if oxygen_count * 2 % metal_count != 0:
        return None
    valence = oxygen_count * 2 // metal_count
    if valence not in elements[metal]["valence"]:
        return None
    return valence


def classify(formula: str, elements: dict, r1: dict) -> str:
    composition = as_map(parse_composition(formula, elements))
    if formula in r1["special_class"]:
        return r1["special_class"][formula]
    if len(composition) == 1:
        symbol = next(iter(composition))
        if elements[symbol]["type"] == "kim_loai":
            return "don_chat_kim_loai"
        return "don_chat_phi_kim"
    if set(composition) == {"H", "O"} and formula == "H2O":
        return "oxit_trung_tinh"
    if len(composition) == 2 and "O" in composition:
        other = next(symbol for symbol in composition if symbol != "O")
        if oxide_valence(formula, composition, elements) is None:
            return "oxit_hon_hop"
        if formula in r1["neutral_oxides"]:
            return "oxit_trung_tinh"
        if "luong_tinh" in elements[other].get("groups", []):
            return "oxit_luong_tinh"
        if elements[other]["type"] == "phi_kim":
            return "oxit_axit"
        return "oxit_bazo"
    parts = split_formula(formula, r1["anions"])
    charge = _ion_charge(parts, elements)
    if charge != 0:
        raise ChemError(f"{formula} không trung hoà điện tích theo R1.")
    if parts["anion"]["formula"] == "OH" and parts["cation"] != "H":
        if cation_charge(parts["cation"], elements) is None and parts["cation"] != "NH4":
            element = elements.get(parts["cation"])
            if not element or element["type"] != "kim_loai":
                raise ChemError(f"{formula} không phải bazơ hợp lệ.")
        return "bazo"
    if parts["cation"] == "H":
        return "axit"
    if parts["anion"]["formula"] in r1["acid_salt_anions"]:
        return "muoi_axit"
    return "muoi_trung_hoa"


def _ion_charge(parts: dict, elements: dict) -> int:
    cation = parts["cation"]
    if cation == "H":
        metal_charge = 1
    elif cation == "NH4":
        metal_charge = 1
    else:
        element = elements[cation]
        anion_charge = parts["anion"]["charge"]
        # Chọn hoá trị có trong bảng để tổng điện tích bằng 0.
        metal_charge = None
        for valence in element["valence"]:
            total = valence * parts["cation_count"] + anion_charge * parts["anion_count"]
            if total == 0:
                metal_charge = valence
                break
        if metal_charge is None:
            return 1
    return metal_charge * parts["cation_count"] + parts["anion"]["charge"] * parts["anion_count"]


def valence_in_compound(formula: str, elements: dict, r1: dict) -> int | None:
    composition = as_map(parse_composition(formula, elements))
    if len(composition) == 2 and "O" in composition:
        return oxide_valence(formula, composition, elements)
    try:
        parts = split_formula(formula, r1["anions"])
    except ChemError:
        return None
    if parts["cation"] in {"H", "NH4"}:
        return 1
    for valence in elements[parts["cation"]]["valence"]:
        total = valence * parts["cation_count"] + parts["anion"]["charge"] * parts["anion_count"]
        if total == 0:
            return valence
    return None


def solubility_rule(cation: str, anion: str, r1: dict) -> tuple[str, str]:
    for rule in r1["solubility"]:
        when = rule["when"]
        if when["cation_in"] and cation not in when["cation_in"]:
            continue
        if when["anion_in"] and anion not in when["anion_in"]:
            continue
        if when["anion"] is not None and anion != when["anion"]:
            continue
        if when["cation"] is not None and cation != when["cation"]:
            continue
        return rule["result"], rule["id"]
    return "chua_ro", ""


def solubility_of(cation: str, anion: str, r1: dict) -> str:
    return solubility_rule(cation, anion, r1)[0]


def molar_mass(composition: list[dict], elements: dict) -> Fraction:
    total = Fraction(0)
    for item in composition:
        total += Fraction(str(elements[item["element"]]["mass"])) * item["quantity"]
    return total


def _rref(rows: list[list[Fraction]]) -> tuple[list[list[Fraction]], dict[int, int]]:
    matrix = [row[:] for row in rows]
    if not matrix:
        return matrix, {}
    row_count = len(matrix)
    col_count = len(matrix[0])
    pivot_of_col: dict[int, int] = {}
    row = 0
    for col in range(col_count):
        pivot = next((i for i in range(row, row_count) if matrix[i][col] != 0), None)
        if pivot is None:
            continue
        matrix[row], matrix[pivot] = matrix[pivot], matrix[row]
        scale = matrix[row][col]
        matrix[row] = [value / scale for value in matrix[row]]
        for other in range(row_count):
            if other != row and matrix[other][col] != 0:
                factor = matrix[other][col]
                matrix[other] = [
                    matrix[other][j] - factor * matrix[row][j] for j in range(col_count)
                ]
        pivot_of_col[col] = row
        row += 1
        if row == row_count:
            break
    return matrix, pivot_of_col


def balance(reactants: list[str], products: list[str], compositions: dict[str, dict]) -> list[int] | None:
    """Tìm hệ số nguyên dương nhỏ nhất để mỗi nguyên tố được bảo toàn."""
    species = reactants + products
    if len(species) < 2:
        return None
    elements = sorted({symbol for formula in species for symbol in compositions[formula]})
    rows = []
    for symbol in elements:
        row = []
        for index, formula in enumerate(species):
            sign = 1 if index < len(reactants) else -1
            row.append(Fraction(sign * compositions[formula].get(symbol, 0)))
        rows.append(row)
    reduced, pivots = _rref(rows)
    free = [col for col in range(len(species)) if col not in pivots]
    if not free:
        return None

    def vector_for(free_values: list[int]) -> list[Fraction] | None:
        values = [Fraction(0) for _ in species]
        for col, value in zip(free, free_values):
            values[col] = Fraction(value)
        for col, pivot_row in pivots.items():
            total = sum(reduced[pivot_row][free_col] * values[free_col] for free_col in free)
            values[col] = -total
        if any(value <= 0 for value in values):
            return None
        return values

    candidates = [1] if len(free) == 1 else None
    found = None
    if candidates is not None:
        found = vector_for([1])
    else:
        from itertools import product

        for guess in product(range(1, 7), repeat=len(free)):
            found = vector_for(list(guess))
            if found is not None:
                break
    if found is None:
        return None
    denominators = [value.denominator for value in found]
    scale = reduce(_lcm, denominators, 1)
    integers = [int(value * scale) for value in found]
    divisor = reduce(gcd, integers)
    return [value // divisor for value in integers]


def format_term(coeff: int, formula: str) -> str:
    return formula if coeff == 1 else f"{coeff}{formula}"


def format_equation(reactants: list[tuple[str, int]], products: list[tuple[str, int]], condition: str = "") -> str:
    left = " + ".join(format_term(coeff, formula) for formula, coeff in reactants)
    right = " + ".join(format_term(coeff, formula) for formula, coeff in products)
    arrow = f" →[{condition}] " if condition else " → "
    return left + arrow + right
