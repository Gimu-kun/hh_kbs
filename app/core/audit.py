"""Đối chiếu phản ứng tham chiếu với sản phẩm do luật sinh ra.

Hàm này đọc danh sách phản ứng được truyền vào, không tự mở reactions.json.
"""

from __future__ import annotations

from collections import defaultdict

from app.core.forward import propose, reaction_signature
from app.core.species import Catalog


def _classes(formulas: list[str], catalog: Catalog) -> str:
    names = []
    for formula in formulas:
        species = catalog.get(formula)
        names.append(species.kind if species else "?")
    return "+".join(names)


def audit_reference(reactions: list[dict], rules: list[dict], catalog: Catalog) -> dict:
    by_input: dict[tuple, set[tuple]] = defaultdict(set)
    for reaction in reactions:
        key = (reaction.get("condition") or "NONE", tuple(sorted(reaction["reactants"])))
        by_input[key].add(tuple(sorted(reaction["products"])))

    correct = 0
    wrong = []
    missing = []
    extra_seen: set[tuple] = set()
    extras = []
    seen_inputs: set[tuple] = set()

    for reaction in reactions:
        condition = reaction.get("condition") or "NONE"
        candidates = propose(reaction["reactants"], condition, rules, catalog)
        target = reaction_signature(reaction["reactants"], reaction["products"], condition)
        produced = {reaction_signature(item["reactants"], item["products"], item["condition"]): item for item in candidates}
        if target in produced:
            correct += 1
        elif produced:
            sample = next(iter(produced.values()))
            wrong.append(
                {
                    "id": reaction.get("id"),
                    "condition": condition,
                    "type": reaction.get("type"),
                    "reactants": reaction["reactants"],
                    "expected": reaction["products"],
                    "got": sample["products"],
                    "rule_id": sample.get("rule_id"),
                }
            )
        else:
            missing.append(
                {
                    "id": reaction.get("id"),
                    "condition": condition,
                    "type": reaction.get("type"),
                    "classes": _classes(reaction["reactants"], catalog),
                    "arity": len(reaction["reactants"]),
                }
            )

        input_key = (condition, tuple(sorted(reaction["reactants"])))
        if input_key in seen_inputs:
            continue
        seen_inputs.add(input_key)
        for item in candidates:
            products = tuple(sorted(item["products"]))
            if products in by_input[input_key]:
                continue
            signature = reaction_signature(item["reactants"], item["products"], item["condition"])
            if signature in extra_seen:
                continue
            extra_seen.add(signature)
            extras.append(item)

    groups: dict[tuple, int] = defaultdict(int)
    for item in missing:
        groups[(item["type"], item["condition"], item["classes"], item["arity"])] += 1
    grouped = [
        {"type": key[0], "condition": key[1], "classes": key[2], "arity": key[3], "count": count}
        for key, count in sorted(groups.items(), key=lambda pair: -pair[1])
    ]
    total = len(reactions)
    return {
        "total": total,
        "correct": correct,
        "wrong": len(wrong),
        "missing": len(missing),
        "extra": len(extras),
        "rate": correct / total if total else 0,
        "missing_groups": grouped,
        "wrong_examples": wrong[:12],
        "extras": extras,
    }
