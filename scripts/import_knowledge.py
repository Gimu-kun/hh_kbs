"""Đọc tài liệu thu thập, chuẩn hoá và ghi các file JSON của mô hình."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.balancer import BalanceError, balance_formulas
from app.core.constants import (
    ACTIVITY_SERIES,
    ALKALI_METALS,
    ALKALINE_EARTH,
    CLASS_LABELS,
    CLASS_ONTOLOGY,
    ELEMENT_TYPE_LABELS,
    GAS_FORMULAS,
    REACTION_TYPE_LABELS,
    SOLUBILITY_LABELS,
    STATE_LABELS,
)
from app.core.formula import FormulaError, parse_formula
from app.core.numbers import to_fraction
from scripts.static_knowledge import CONDITIONS, FORMULAS, HEURISTICS, REAGENTS, RULES, TEMPLATES

DATA_DIR = ROOT / "data"
ROMAN = {
    "0": 0, "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8,
}
CLASS_PRIORITY = {
    "oxit_luong_tinh": 50,
    "oxit_trung_tinh": 40,
    "oxit_axit": 30,
    "oxit_bazo": 20,
    "bazo_khong_tan": 30,
    "bazo_tan": 20,
    "muoi_axit": 20,
    "muoi_trung_hoa": 10,
}
CLASS_OVERRIDES = {
    "CO": "oxit_trung_tinh",
    "NO": "oxit_trung_tinh",
    "N2O": "oxit_trung_tinh",
    "CO2": "oxit_axit",
    "SO2": "oxit_axit",
    "SO3": "oxit_axit",
    "P2O5": "oxit_axit",
    "N2O5": "oxit_axit",
    "SiO2": "oxit_axit",
    "Al2O3": "oxit_luong_tinh",
    "ZnO": "oxit_luong_tinh",
    "Cr2O3": "oxit_luong_tinh",
    "BeO": "oxit_luong_tinh",
    "PbO": "oxit_luong_tinh",
    "PbO2": "oxit_luong_tinh",
    "SnO": "oxit_luong_tinh",
    "SnO2": "oxit_luong_tinh",
    "H2O": "oxit_trung_tinh",
    "Fe3O4": "oxit_bazo",
    "Fe2O3": "oxit_bazo",
    "FeO": "oxit_bazo",
    "CuO": "oxit_bazo",
    "CaO": "oxit_bazo",
}
INORGANIC_CARBON = {"CO", "CO2", "H2CO3", "HCN", "HOCN", "HNCO", "HSCN", "(NH4)2CO3", "NH4HCO3", "NH4CN"}
DROPPED_CLASSES = {"axit huu co", "hop chat huu co", "hidrocacbon khong no", "hidrocacbon no", "khi doc"}


def fold(text: str) -> str:
    lowered = text.lower().strip()
    table = str.maketrans(
        "áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ",
        "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd",
    )
    return " ".join(lowered.translate(table).split())


def write_collection(name: str, items: list[dict]) -> None:
    path = DATA_DIR / name
    path.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_text() -> str:
    docx = next(ROOT.glob("thu thap tri thuc.docx"))
    result = subprocess.run(["textutil", "-convert", "txt", "-stdout", str(docx)], check=True, capture_output=True)
    return result.stdout.decode("utf-8")


def section(lines: list[str], start: str, end: str) -> list[str]:
    start_index = next(index for index, line in enumerate(lines) if start in line)
    end_index = next(index for index, line in enumerate(lines) if end in line and index > start_index)
    return lines[start_index:end_index]


def nonempty(lines: list[str]) -> list[str]:
    return [line.strip() for line in lines if line.strip()]


def parse_valence(text: str) -> list[int]:
    values = []
    for part in re.split(r"[,;\s]+", text.strip()):
        if part in ROMAN:
            values.append(ROMAN[part])
    return values


def parse_elements(lines: list[str]) -> list[dict]:
    rows = nonempty(lines)
    items = []
    index = 0
    while index + 5 < len(rows):
        symbol = rows[index]
        if not re.fullmatch(r"[A-Z][a-z]?", symbol):
            index += 1
            continue
        name, atomic, mass, valence, element_type = rows[index + 1:index + 6]
        if not atomic.isdigit() or not re.fullmatch(r"\d+(?:\.\d+)?", mass):
            index += 1
            continue
        folded_type = fold(element_type)
        if folded_type not in {"kim loai", "phi kim", "khi hiem"}:
            index += 1
            continue
        type_code = {"kim loai": "kim_loai", "phi kim": "phi_kim", "khi hiem": "khi_hiem"}[folded_type]
        cursor = index + 6
        activity = None
        if cursor < len(rows) and re.fullmatch(r"\d+", rows[cursor]):
            activity = int(rows[cursor])
            cursor += 1
        groups = []
        if symbol in ALKALI_METALS:
            groups.append("kiem")
        if symbol in ALKALINE_EARTH:
            groups.append("kiem_tho")
        mass_number = float(mass)
        items.append(
            {
                "symbol": symbol,
                "name": name,
                "z": int(atomic),
                "mass": int(mass_number) if mass_number.is_integer() else mass_number,
                "valence": parse_valence(valence),
                "type": type_code,
                "type_label": ELEMENT_TYPE_LABELS[type_code],
                "activity": activity,
                "groups": groups,
            }
        )
        index = cursor
    by_symbol = {}
    for item in items:
        by_symbol[item["symbol"]] = item
    for position, symbol in enumerate(ACTIVITY_SERIES, start=1):
        if symbol in by_symbol:
            by_symbol[symbol]["activity"] = position
    for item in by_symbol.values():
        if item["symbol"] not in ACTIVITY_SERIES:
            item["activity"] = None
    return [by_symbol[symbol] for symbol in sorted(by_symbol, key=lambda value: by_symbol[value]["z"])]


def map_class(label: str) -> str | None:
    folded = fold(label)
    if folded in DROPPED_CLASSES:
        return None
    table = {
        "don chat kim loai": "don_chat_kim_loai",
        "don chat phi kim": "don_chat_phi_kim",
        "don chat khi hiem": "don_chat_khi_hiem",
        "oxit bazo": "oxit_bazo",
        "oxit bazow": "oxit_bazo",
        "oxit axit": "oxit_axit",
        "oxit luong tinh": "oxit_luong_tinh",
        "oxit trung tinh": "oxit_trung_tinh",
        "axit": "axit",
        "axit yeu": "axit",
        "bazo tan": "bazo_tan",
        "bazo khong tan": "bazo_khong_tan",
        "muoi trung hoa": "muoi_trung_hoa",
        "muoi axit": "muoi_axit",
        "hidrua kim loai": "hidrua_kim_loai",
        "hop chat khac": "hop_chat_khac",
    }
    return table.get(folded, "hop_chat_khac")


def map_state(label: str) -> str:
    folded = fold(label)
    return {"ran": "ran", "long": "long", "khi": "khi", "dung dich": "dung_dich"}.get(folded, "ran")


def map_soluble(label: str) -> str:
    folded = fold(label)
    return {
        "tan": "tan",
        "it tan": "it_tan",
        "khong tan": "khong_tan",
        "phan ung voi nuoc": "phan_ung_nuoc",
    }.get(folded, "chua_ro")


def is_formula_line(text: str) -> bool:
    if not re.fullmatch(r"[A-Z(][A-Za-z0-9()\[\]]*", text):
        return False
    if re.fullmatch(r"[A-Z][a-z]{3,}", text):
        return False
    return True


def composition_signature(formula: str) -> tuple:
    composition = parse_formula(formula)
    return tuple(sorted(composition.items()))


def is_composition_line(text: str) -> bool:
    return bool(re.search(r"[A-Z][a-z]?\s*:\s*\d+", text))


def is_organic(formula: str, elements: dict[str, dict]) -> bool:
    if formula in INORGANIC_CARBON:
        return False
    try:
        composition = parse_formula(formula)
    except FormulaError:
        return False
    if "C" not in composition:
        return False
    has_metal = any(elements.get(symbol, {}).get("type") == "kim_loai" for symbol in composition)
    organic_pattern = re.search(r"CH3|C2H5|C6H|C\d*H\d+", formula)
    if organic_pattern:
        return True
    if "H" in composition and not has_metal and formula not in INORGANIC_CARBON:
        return True
    return False


def compound_record(formula: str, name: str, class_code: str, state: str, soluble: str, elements: dict) -> dict:
    composition = parse_formula(formula)
    total = to_fraction(0)
    for symbol, count in composition.items():
        total += to_fraction(elements[symbol]["mass"]) * count
    molar_mass = total.numerator if total.denominator == 1 else float(total)
    return {
        "formula": formula,
        "name": name or formula,
        "class": class_code,
        "class_label": CLASS_LABELS[class_code],
        "ontology": CLASS_ONTOLOGY[class_code],
        "composition": composition,
        "state": state,
        "state_label": STATE_LABELS[state],
        "soluble": soluble,
        "soluble_label": SOLUBILITY_LABELS[soluble],
        "charge": 0,
        "molar_mass": molar_mass,
    }


def parse_compounds(lines: list[str], elements: dict[str, dict]) -> list[dict]:
    rows = nonempty(lines)
    found: dict[str, dict] = {}
    index = 0
    while index < len(rows):
        if not is_formula_line(rows[index]):
            index += 1
            continue
        window = rows[index + 1:index + 7]
        composition_at = next((offset for offset, line in enumerate(window) if is_composition_line(line)), None)
        if composition_at is None or composition_at < 2:
            index += 1
            continue
        formula = rows[index]
        name = rows[index + 1]
        class_label = rows[index + 2] if composition_at >= 2 else ""
        rest = window[composition_at + 1:]
        try:
            if formula not in elements and not parse_formula(formula):
                raise FormulaError(formula)
            parse_formula(formula)
        except FormulaError:
            index += 1
            continue
        if any(symbol not in elements for symbol in parse_formula(formula)):
            index += 1
            continue
        if is_organic(formula, elements):
            index += 1
            continue
        class_code = map_class(class_label)
        if class_code is None:
            index += 1
            continue
        state = map_state(rest[0]) if rest else "ran"
        soluble = map_soluble(rest[1]) if len(rest) > 1 else "chua_ro"
        try:
            record = compound_record(formula, name, class_code, state, soluble, elements)
        except KeyError:
            index += 1
            continue
        current = found.get(formula)
        if current is None or CLASS_PRIORITY.get(class_code, 0) >= CLASS_PRIORITY.get(current["class"], 0):
            found[formula] = record
        index += composition_at + 4
    for formula, class_code in CLASS_OVERRIDES.items():
        if formula in found:
            found[formula]["class"] = class_code
            found[formula]["class_label"] = CLASS_LABELS[class_code]
            found[formula]["ontology"] = CLASS_ONTOLOGY[class_code]
    return list(found.values())


def normalize_condition(raw: str) -> str:
    folded = fold(raw)
    heat = "t°" in raw or "dun" in folded or "nong" in folded or "nhiet" in folded
    catalyst = any(token in folded for token in ("xuc tac", "xt", "mno2", "v2o5"))
    dilute = "loang" in folded
    concentrated = "dac" in folded
    melt = "nong chay" in folded or "dpnc" in folded
    electrolysis = "dien phan" in folded or "dpdd" in folded or melt
    light = "anh sang" in folded
    pressure = "ap suat" in folded
    if melt:
        return "ELECTROLYSIS_MELT"
    if electrolysis:
        return "ELECTROLYSIS_SOLUTION"
    if heat and catalyst:
        return "HEAT_CATALYST"
    if concentrated and heat:
        return "CONC_HEAT"
    if dilute and heat:
        return "DILUTE_HEAT"
    if heat and light:
        return "HEAT_LIGHT"
    if heat and pressure:
        return "HEAT_PRESSURE"
    if heat:
        return "HEAT"
    if concentrated:
        return "CONC"
    if dilute:
        return "DILUTE"
    if catalyst:
        return "CATALYST"
    if light:
        return "LIGHT"
    if pressure:
        return "PRESSURE"
    if folded in {"khong", "none", "khong can dieu kien"}:
        return "NONE"
    if folded:
        return "OTHER"
    return "NONE"


def normalize_type(raw: str) -> str:
    folded = fold(raw)
    if "trung hoa" in folded:
        return "trung_hoa"
    if "oxi hoa" in folded:
        return "oxi_hoa_khu"
    if "hoa hop" in folded:
        return "hoa_hop"
    if "phan huy" in folded:
        return "phan_huy"
    if "dien phan" in folded:
        return "dien_phan"
    if "trao doi" in folded:
        return "trao_doi"
    if "the" in folded:
        return "the"
    return "khac"


def clean_species(token: str) -> str | None:
    text = token.strip()
    if " (" in text:
        text = text.split(" (", 1)[0].strip()
    text = text.replace(" ", "")
    if not is_formula_line(text):
        return None
    try:
        parse_formula(text)
    except FormulaError:
        return None
    return text


def parse_reactions(lines: list[str], elements: dict[str, dict]) -> tuple[list[dict], dict]:
    rows = nonempty(lines)
    reactions = []
    seen = set()
    stats = {"raw": 0, "organic": 0, "invalid": 0, "unbalanced": 0, "kept": 0}
    index = 0
    while index < len(rows):
        if not re.fullmatch(r"R\d+", rows[index]):
            index += 1
            continue
        if index + 6 < len(rows) and not re.fullmatch(r"R\d+", rows[index + 6]) and index + 6 != len(rows):
            # Khối lệch nhịp: nhảy tới mã kế tiếp.
            if not (index + 6 == len(rows) or re.fullmatch(r"R\d+", rows[index + 6])):
                index += 1
                continue
        if index + 5 >= len(rows):
            break
        if index + 6 < len(rows) and not re.fullmatch(r"R\d+", rows[index + 6]):
            index += 1
            continue
        stats["raw"] += 1
        reaction_id, reactant_text, product_text, coefficient_text, condition_text, type_text = rows[index:index + 6]
        reactants = [clean_species(part) for part in reactant_text.split(",")]
        products = [clean_species(part) for part in product_text.split(",")]
        if any(item is None for item in reactants + products):
            stats["invalid"] += 1
            index += 6
            continue
        if any(is_organic(item, elements) for item in reactants + products):
            stats["organic"] += 1
            index += 6
            continue
        coefficient_parts = [part.strip() for part in coefficient_text.split(",")]
        if any(not re.fullmatch(r"\d+", part) for part in coefficient_parts):
            stats["invalid"] += 1
            index += 6
            continue
        if len(coefficient_parts) != len(reactants) + len(products):
            stats["invalid"] += 1
            index += 6
            continue
        try:
            balanced = balance_formulas(reactants, products)
        except BalanceError:
            stats["unbalanced"] += 1
            index += 6
            continue
        condition = normalize_condition(condition_text)
        reaction_type = normalize_type(type_text)
        signature = (tuple(reactants), tuple(products), condition)
        if signature in seen:
            index += 6
            continue
        seen.add(signature)
        condition_info = next(item for item in CONDITIONS if item["code"] == condition)
        reactions.append(
            {
                "id": reaction_id,
                "reactants": reactants,
                "products": products,
                "coefficients": balanced["coefficients"],
                "condition": condition,
                "condition_label": condition_info["name"],
                "condition_symbol": condition_info["symbol"],
                "type": reaction_type,
                "type_label": REACTION_TYPE_LABELS[reaction_type],
                "condition_raw": condition_text,
                "source": "collected",
            }
        )
        stats["kept"] += 1
        index += 6
    return reactions, stats


def infer_skeleton(formula: str, elements: dict[str, dict]) -> dict | None:
    try:
        composition = parse_formula(formula)
    except FormulaError:
        return None
    if any(symbol not in elements for symbol in composition):
        return None
    if is_organic(formula, elements):
        return None
    symbols = list(composition)
    metals = [symbol for symbol in symbols if elements[symbol]["type"] == "kim_loai"]
    other_nonmetals = [symbol for symbol in symbols if symbol != "O" and elements[symbol]["type"] != "kim_loai"]
    if len(symbols) == 1 or formula in GAS_FORMULAS or formula in {"Br2", "I2", "P4", "S8"}:
        element = symbols[0]
        if elements[element]["type"] == "kim_loai":
            class_code, state, soluble = "don_chat_kim_loai", "ran", "khong_tan"
        elif elements[element]["type"] == "khi_hiem":
            class_code, state, soluble = "don_chat_khi_hiem", "khi", "it_tan"
        else:
            class_code = "don_chat_phi_kim"
            state = "khi" if formula in GAS_FORMULAS else "ran"
            soluble = "it_tan" if state == "khi" else "khong_tan"
    elif formula.endswith("OH") or "(OH)" in formula:
        class_code, state, soluble = "bazo_khong_tan", "ran", "khong_tan"
    elif formula.startswith("H") and formula not in {"H2O"}:
        class_code, state, soluble = "axit", "dung_dich", "tan"
    elif "O" in composition and metals and not other_nonmetals:
        class_code, state, soluble = "oxit_bazo", "ran", "khong_tan"
    elif metals or formula.startswith("(NH4)"):
        class_code, state, soluble = "muoi_trung_hoa", "ran", "chua_ro"
    else:
        class_code, state, soluble = "hop_chat_khac", "ran", "chua_ro"
    if formula in GAS_FORMULAS:
        state = "khi"
    if formula in CLASS_OVERRIDES:
        class_code = CLASS_OVERRIDES[formula]
    return compound_record(formula, formula, class_code, state, soluble, elements)


def _formula_rank(formula: str, compounds: dict[str, dict]) -> tuple:
    record = compounds[formula]
    return (
        0 if record["name"] != formula else 1,
        1 if formula.startswith("(") else 0,
        len(formula),
        formula,
    )


def _canonicalize(formula: str, canonical: dict[tuple, str]) -> str:
    return canonical.get(composition_signature(formula), formula)


def _dedupe_reactions(reactions: list[dict]) -> list[dict]:
    seen = set()
    kept = []
    for reaction in reactions:
        signature = (tuple(reaction["reactants"]), tuple(reaction["products"]), reaction["condition"])
        if signature in seen:
            continue
        seen.add(signature)
        kept.append(reaction)
    return kept


def main() -> None:
    text = extract_text()
    lines = text.splitlines()
    elements = parse_elements(section(lines, "CÁC NGUYÊN TỐ HÓA HỌC", "CÁC CHẤT VÀ HỢP CHẤT"))
    element_map = {item["symbol"]: item for item in elements}
    compounds = {
        item["formula"]: item
        for item in parse_compounds(section(lines, "CÁC CHẤT VÀ HỢP CHẤT", "CÁC PHẢN ỨNG HÓA HỌC CỤ THỂ"), element_map)
    }
    reactions, stats = parse_reactions(section(lines, "CÁC PHẢN ỨNG HÓA HỌC CỤ THỂ", "LUẬT PHẢN ỨNG"), element_map)
    canonical = {}
    for formula in compounds:
        signature = composition_signature(formula)
        current = canonical.get(signature)
        if current is None or _formula_rank(formula, compounds) < _formula_rank(current, compounds):
            canonical[signature] = formula
    rewritten = []
    for reaction in reactions:
        try:
            reaction["reactants"] = [_canonicalize(formula, canonical) for formula in reaction["reactants"]]
            reaction["products"] = [_canonicalize(formula, canonical) for formula in reaction["products"]]
            balanced = balance_formulas(reaction["reactants"], reaction["products"])
        except (FormulaError, BalanceError):
            continue
        reaction["coefficients"] = balanced["coefficients"]
        rewritten.append(reaction)
    reactions = _dedupe_reactions(rewritten)
    for reaction in reactions:
        for formula in reaction["reactants"] + reaction["products"]:
            if formula not in compounds:
                skeleton = infer_skeleton(formula, element_map)
                if skeleton:
                    compounds[formula] = skeleton
    usable = []
    for reaction in reactions:
        if all(formula in compounds for formula in reaction["reactants"] + reaction["products"]):
            usable.append(reaction)
    reagents = [item for item in REAGENTS if item["formula"] in compounds]
    missing_reagents = [item["formula"] for item in REAGENTS if item["formula"] not in compounds]
    DATA_DIR.mkdir(exist_ok=True)
    write_collection("elements.json", elements)
    write_collection("compounds.json", sorted(compounds.values(), key=lambda item: item["formula"]))
    write_collection("reactions.json", usable)
    write_collection("rules.json", RULES)
    write_collection("conditions.json", CONDITIONS)
    write_collection("heuristics.json", HEURISTICS)
    write_collection("formulas.json", FORMULAS)
    write_collection("reagents.json", reagents)
    write_collection("templates.json", TEMPLATES)
    print(f"elements={len(elements)} compounds={len(compounds)} reactions={len(usable)}")
    print("reaction_stats", stats)
    print("missing_reagents", missing_reagents)


if __name__ == "__main__":
    main()
