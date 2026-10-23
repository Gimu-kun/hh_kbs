"""Ghi ion, gốc axit, hóa trị, số oxi hóa và tính tan suy ra vào elements.json và compounds.json.

Nguồn quy tắc nằm ở data/property_notes.json và app/core/species.py.
Không ghi đè tính tan đã có giá trị khác chua_ro.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.species import derived_compound_fields, element_oxidation_states
from app.core.constants import SOLUBILITY_LABELS

DATA = ROOT / "data"


def main() -> None:
    elements_path = DATA / "elements.json"
    compounds_path = DATA / "compounds.json"
    elements_payload = json.loads(elements_path.read_text(encoding="utf-8"))
    compounds_payload = json.loads(compounds_path.read_text(encoding="utf-8"))
    elements = {item["symbol"]: item for item in elements_payload["items"]}
    filled = 0
    for element in elements_payload["items"]:
        states = element_oxidation_states(element)
        element["oxidation_states"] = states
        element["ion_charges"] = [value for value in states if value > 0] if element.get("type") == "kim_loai" else []
        element["property_basis"] = "sgk_oxidation_sign"
    for compound in compounds_payload["items"]:
        derived = derived_compound_fields(compound, elements)
        if compound.get("soluble") == "chua_ro" and derived["soluble"] != "chua_ro":
            filled += 1
        compound["soluble"] = derived["soluble"]
        compound["soluble_label"] = SOLUBILITY_LABELS.get(derived["soluble"], compound.get("soluble_label"))
        compound["ions"] = derived["ions"]
        compound["acid_radical"] = derived["acid_radical"]
        compound["metal_valence"] = derived["metal_valence"]
        compound["oxidation"] = derived["oxidation"]
        compound["soluble_basis"] = derived["soluble_basis"]
    elements_path.write_text(json.dumps(elements_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    compounds_path.write_text(json.dumps(compounds_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã bổ sung {len(elements_payload['items'])} nguyên tố, {len(compounds_payload['items'])} chất, điền tan cho {filled} chất còn chua_ro.")


if __name__ == "__main__":
    main()
