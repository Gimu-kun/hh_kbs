"""Ghép một bước phản ứng với luật if-then trong hệ luật L."""

from __future__ import annotations


def class_matches(actual: str | None, expected: str) -> bool:
    if not actual:
        return False
    if actual == expected:
        return True
    families = {
        "muoi": "muoi",
        "oxit": "oxit",
        "bazo": "bazo",
        "don_chat": "don_chat",
        "axit": "axit",
    }
    prefix = families.get(expected)
    if prefix and (actual == prefix or actual.startswith(prefix + "_")):
        return True
    return False


def _compound_matches_class(compound: dict | None, names: list[str]) -> bool:
    if compound is None:
        return False
    return any(class_matches(compound.get("class"), name) for name in names)


def match_rule(
    main: str,
    edge: dict,
    compounds: dict[str, dict],
    elements: dict[str, dict],
    rules: list[dict],
) -> dict | None:
    main_compound = compounds.get(main)
    reactant_formulas = [formula for formula in edge["reactants"] if formula != main]
    product_formulas = edge["products"]
    best = None
    best_score = -1
    for rule in rules:
        spec = rule.get("match") or {}
        if not _fits(main, main_compound, reactant_formulas, product_formulas, edge, compounds, elements, spec):
            continue
        score = int(rule.get("priority") or 0) * 10 + len(spec)
        if score > best_score:
            best = rule
            best_score = score
    return best


def _fits(main, main_compound, reactant_formulas, product_formulas, edge, compounds, elements, spec) -> bool:
    if spec.get("main_class") and not _compound_matches_class(main_compound, spec["main_class"]):
        return False
    if spec.get("main_formula") and main not in spec["main_formula"]:
        return False
    if spec.get("main_formula_not") and main in spec["main_formula_not"]:
        return False
    if spec.get("main_groups_any"):
        groups = set((elements.get(main) or {}).get("groups") or [])
        if not groups.intersection(spec["main_groups_any"]):
            return False
    if spec.get("main_before_hydrogen"):
        metal = elements.get(main) or {}
        hydrogen = elements.get("H") or {}
        metal_activity = metal.get("activity")
        hydrogen_activity = hydrogen.get("activity")
        if metal_activity is None or hydrogen_activity is None or metal_activity >= hydrogen_activity:
            return False
    if spec.get("aux_class_any"):
        if not any(_compound_matches_class(compounds.get(formula), spec["aux_class_any"]) for formula in reactant_formulas):
            return False
    if spec.get("aux_formula_any"):
        if not any(formula in spec["aux_formula_any"] for formula in reactant_formulas):
            return False
    if spec.get("product_class_any"):
        if not any(_compound_matches_class(compounds.get(formula), spec["product_class_any"]) for formula in product_formulas):
            return False
    if spec.get("product_formula_any"):
        if not any(formula in spec["product_formula_any"] for formula in product_formulas):
            return False
    if spec.get("type") and edge.get("type") not in spec["type"]:
        return False
    if spec.get("condition") and edge.get("condition") not in spec["condition"]:
        return False
    if spec.get("condition_not") and edge.get("condition") in spec["condition_not"]:
        return False
    return True
