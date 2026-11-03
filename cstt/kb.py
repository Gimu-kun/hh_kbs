"""Nạp cơ sở tri thức và kiểm tra từng chất bằng R1."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from cstt.chem import (
    ChemError,
    as_map,
    classify,
    parse_composition,
    solubility_of,
    split_formula,
    valence_in_compound,
)

ROOT = Path(__file__).resolve().parent.parent
CONCEPT = ROOT / "kb" / "concept"
RULES = ROOT / "kb" / "rules"


def load_json(folder: Path, name: str) -> dict:
    with (folder / name).open(encoding="utf-8") as handle:
        return json.load(handle)


@dataclass
class Compound:
    formula: str
    name: str
    class_id: str
    class_label: str
    composition: list[dict]
    comp: dict[str, int]
    state: str
    state_label: str
    ions: dict | None = None
    valence: int | None = None
    solubility: str | None = None


@dataclass
class KnowledgeBase:
    elements: dict
    compounds: dict[str, Compound]
    r1: dict
    r2: dict
    formulas: dict
    conditions: dict
    class_names: dict[str, str] = field(default_factory=dict)

    def is_a(self, class_id: str, parent: str) -> bool:
        current = class_id
        seen = set()
        while current and current not in seen:
            if current == parent:
                return True
            seen.add(current)
            current = self.class_parent.get(current)
        return False


def load_kb() -> KnowledgeBase:
    elements = {item["symbol"]: item for item in load_json(CONCEPT, "elements.json")["items"]}
    r1 = load_json(RULES, "constraints.json")
    class_names = {item["id"]: item["name"] for item in r1["classes"]}
    parent = {}
    for item in r1["classes"]:
        for child in item["children"]:
            parent[child] = item["id"]
    compounds: dict[str, Compound] = {}
    for raw in load_json(CONCEPT, "compounds.json")["items"]:
        formula = raw["formula"]
        composition = parse_composition(formula, elements)
        if composition != raw["composition"]:
            raise ChemError(
                f"Thành phần của {formula} không khớp công thức. "
                f"Suy ra {composition}, dữ liệu ghi {raw['composition']}."
            )
        class_id = classify(formula, elements, r1)
        if class_id != raw["class"]:
            raise ChemError(f"R1 xếp {formula} là {class_id}, dữ liệu ghi {raw['class']}.")
        ions = None
        valence = None
        solubility = None
        if class_id.startswith("oxit") and class_id != "oxit_hon_hop":
            valence = valence_in_compound(formula, elements, r1)
        if class_id in {"axit", "bazo", "muoi_trung_hoa", "muoi_axit"}:
            ions = split_formula(formula, r1["anions"])
            valence = valence_in_compound(formula, elements, r1)
            if class_id != "axit":
                solubility = solubility_of(ions["cation"], ions["anion"]["formula"], r1)
        compound = Compound(
            formula=formula,
            name=raw["name"],
            class_id=class_id,
            class_label=raw["class_label"],
            composition=composition,
            comp=as_map(composition),
            state=raw["state"],
            state_label=raw["state_label"],
            ions=ions,
            valence=valence,
            solubility=solubility,
        )
        compounds[formula] = compound
    kb = KnowledgeBase(
        elements=elements,
        compounds=compounds,
        r1=r1,
        r2=load_json(RULES, "reactions.json"),
        formulas=load_json(RULES, "formulas.json"),
        conditions=load_json(CONCEPT, "conditions.json"),
        class_names=class_names,
    )
    kb.class_parent = parent
    return kb
