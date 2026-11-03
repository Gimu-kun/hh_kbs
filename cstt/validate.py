"""Kiểm tra trùng khoá và tham chiếu của toàn bộ cơ sở tri thức."""

from __future__ import annotations

import json
from collections import Counter

from cstt import kb as kb_paths
from cstt.chem import ChemError
from cstt.reactions import GENERATORS

SOLUBILITY_VALUES = {"tan", "it_tan", "khong_tan"}


def validate_knowledge() -> None:
    elements = _items(kb_paths.CONCEPT / "elements.json")
    compounds = _items(kb_paths.CONCEPT / "compounds.json")
    conditions = _items(kb_paths.CONCEPT / "conditions.json")
    constraints = _read(kb_paths.RULES / "constraints.json")
    reactions = _read(kb_paths.RULES / "reactions.json")
    formulas = _read(kb_paths.RULES / "formulas.json")

    _unique(elements, "symbol", "Ký hiệu nguyên tố")
    _unique(elements, "z", "Số hiệu nguyên tử")
    _unique(elements, "name", "Tên nguyên tố")
    _unique(compounds, "formula", "Công thức")
    _unique(compounds, "name", "Tên hợp chất")
    _unique(conditions, "code", "Mã điều kiện")
    _unique(conditions, "symbol", "Ký hiệu điều kiện")
    _unique(conditions, "name", "Tên điều kiện")
    _unique(constraints["classes"], "id", "Mã lớp")
    _unique(constraints["classes"], "name", "Tên lớp")
    _unique(constraints["anions"], "formula", "Công thức anion")
    _unique(constraints["solubility"], "id", "Mã độ tan")
    _unique(constraints["solubility"], "name", "Tên quy tắc độ tan")
    _unique(reactions["rules"], "id", "Mã luật phản ứng")
    _unique(reactions["rules"], "name", "Tên luật phản ứng")
    _unique(formulas["constants"], "id", "Mã hằng số")
    _unique(formulas["constants"], "symbol", "Ký hiệu hằng số")
    _unique(formulas["constants"], "name", "Tên hằng số")
    _unique(formulas["items"], "id", "Mã công thức")
    _unique(formulas["items"], "name", "Tên công thức")
    _unique_list(constraints["neutral_oxides"], "Oxit trung tính")
    _unique_list(constraints["acid_salt_anions"], "Anion muối axit")

    class_ids = {item["id"] for item in constraints["classes"]}
    class_names = {item["id"]: item["name"] for item in constraints["classes"]}
    _class_tree(constraints["classes"], class_ids)
    element_by_symbol = {item["symbol"]: item for item in elements}
    compound_by_formula = {item["formula"]: item for item in compounds}
    anion_ids = {item["formula"] for item in constraints["anions"]}
    condition_codes = {item["code"] for item in conditions}
    metals = {item["symbol"] for item in elements if item["type"] == "kim_loai"}
    cations = metals | {"NH4"}
    groups = {group for item in elements for group in item["groups"]}

    for compound in compounds:
        class_id = compound["class"]
        if class_id not in class_names:
            raise ChemError(f"Hợp chất {compound['formula']} dùng lớp {class_id} không có trong phân loại.")
        if compound["class_label"] != class_names[class_id]:
            raise ChemError(
                f"Nhãn lớp của {compound['formula']} phải là {class_names[class_id]}."
            )

    for formula, class_id in constraints["special_class"].items():
        if formula not in compound_by_formula:
            raise ChemError(f"Lớp đặc biệt trỏ tới {formula}, chất này không có trong hợp chất.")
        if class_id not in class_ids:
            raise ChemError(f"Lớp đặc biệt của {formula} trỏ tới lớp {class_id} không có trong phân loại.")

    for formula in constraints["neutral_oxides"]:
        compound = compound_by_formula.get(formula)
        if compound is None:
            raise ChemError(f"Oxit trung tính {formula} không có trong hợp chất.")
        if compound["class"] != "oxit_trung_tinh":
            raise ChemError(f"{formula} không thuộc lớp oxit trung tính.")

    for formula in constraints["acid_salt_anions"]:
        if formula not in anion_ids:
            raise ChemError(f"Anion muối axit {formula} không có trong danh sách anion.")

    for rule in constraints["solubility"]:
        when = rule["when"]
        named_cations = ([when["cation"]] if when["cation"] else []) + when["cation_in"]
        named_anions = ([when["anion"]] if when["anion"] else []) + when["anion_in"]
        if not named_cations and not named_anions:
            raise ChemError(f"Quy tắc độ tan {rule['id']} chưa trỏ tới cation hoặc anion nào.")
        if rule["result"] not in SOLUBILITY_VALUES:
            raise ChemError(f"Độ tan {rule['id']} có kết quả {rule['result']} ngoài tan, ít tan và không tan.")
        for cation in named_cations:
            if cation not in cations:
                raise ChemError(f"Độ tan {rule['id']} trỏ cation {cation} không có trong nguyên tố kim loại hoặc NH4.")
        for anion in named_anions:
            if anion not in anion_ids:
                raise ChemError(f"Độ tan {rule['id']} trỏ anion {anion} không có trong danh sách anion.")

    for rule in reactions["rules"]:
        _reaction(rule, class_ids, compound_by_formula, anion_ids, condition_codes, metals, cations, groups)


def _reaction(rule, class_ids, compounds, anions, conditions, metals, cations, groups) -> None:
    rule_id = rule["id"]
    if rule["kind"] not in GENERATORS:
        raise ChemError(f"Luật {rule_id} có kind {rule['kind']} mà máy sinh phản ứng không biết.")
    for class_id in rule["classes"]:
        if class_id not in class_ids:
            raise ChemError(f"Luật {rule_id} dùng lớp {class_id} không có trong phân loại.")
    for group in rule["groups"]:
        if group not in groups:
            raise ChemError(f"Luật {rule_id} dùng nhóm {group} không có trên nguyên tố nào.")
    for code in rule["conditions"]:
        if code not in conditions:
            raise ChemError(f"Luật {rule_id} dùng điều kiện {code} không có trong danh sách điều kiện.")
    for binding in rule["conditions_for"]:
        if binding["formula"] not in compounds:
            raise ChemError(f"Luật {rule_id} gắn điều kiện cho {binding['formula']}, chất này không có.")
        for code in binding["conditions"]:
            if code not in conditions:
                raise ChemError(f"Luật {rule_id} dùng điều kiện {code} không có trong danh sách điều kiện.")
    for formula in rule["exclude_compounds"]:
        if formula not in compounds:
            raise ChemError(f"Luật {rule_id} loại hợp chất {formula} không có trong cơ sở.")
    for metal in rule["exclude_metals"]:
        if metal not in metals:
            raise ChemError(f"Luật {rule_id} loại kim loại {metal} không có trong nguyên tố kim loại.")
    for formula in rule["exclude_acids"]:
        compound = compounds.get(formula)
        if compound is None or compound["class"] != "axit":
            raise ChemError(f"Luật {rule_id} loại axit {formula} không phải axit trong cơ sở.")
    for anion in rule["exclude_anions"]:
        if anion not in anions:
            raise ChemError(f"Luật {rule_id} loại anion {anion} không có trong danh sách anion.")
    for cation in rule["exclude_cations"]:
        if cation not in cations:
            raise ChemError(f"Luật {rule_id} loại cation {cation} không có trong kim loại hoặc NH4.")
    for value in rule["solubility"] + rule["exclude_solubility"]:
        if value not in SOLUBILITY_VALUES:
            raise ChemError(f"Luật {rule_id} dùng độ tan {value} ngoài tan, ít tan và không tan.")
    for field, label in (("reagent", "Thuốc thử"), ("gas", "Khí")):
        formula = rule[field]
        if formula is not None and formula not in compounds:
            raise ChemError(f"{label} {formula} của luật {rule_id} không có trong hợp chất.")


def _class_tree(classes: list[dict], class_ids: set[str]) -> None:
    parents: dict[str, str] = {}
    for item in classes:
        for child in item["children"]:
            if child not in class_ids:
                raise ChemError(f"Lớp {item['id']} có lớp con {child} không có trong phân loại.")
            if child in parents:
                raise ChemError(f"Lớp {child} đang thuộc cả {parents[child]} và {item['id']}.")
            parents[child] = item["id"]
    for item in classes:
        seen = set()
        current = item["id"]
        while current in parents:
            if current in seen:
                raise ChemError(f"Phân loại có vòng tại lớp {current}.")
            seen.add(current)
            current = parents[current]


def _unique(items: list[dict], field: str, label: str) -> None:
    counts = Counter(item[field] for item in items)
    duplicated = [str(value) for value, count in counts.items() if count > 1]
    if duplicated:
        raise ChemError(f"{label} bị trùng: {', '.join(duplicated)}.")


def _unique_list(items: list[str], label: str) -> None:
    counts = Counter(items)
    duplicated = [value for value, count in counts.items() if count > 1]
    if duplicated:
        raise ChemError(f"{label} bị trùng: {', '.join(duplicated)}.")


def _read(path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _items(path) -> list[dict]:
    return _read(path)["items"]
