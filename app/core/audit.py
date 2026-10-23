"""Đối chiếu phản ứng tham chiếu với sản phẩm do luật sinh ra.

Hàm này đọc danh sách phản ứng được truyền vào, không tự mở reactions.json.
"""

from __future__ import annotations

from collections import defaultdict

from app.core.forward import primary_candidate, propose, reaction_signature
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
    loose = 0
    single = 0
    wrong = []
    missing = []
    extra_seen: set[tuple] = set()
    extras = []
    seen_inputs: set[tuple] = set()

    for reaction in reactions:
        condition = reaction.get("condition") or "NONE"
        candidates = propose(reaction["reactants"], condition, rules, catalog)
        target_products = tuple(sorted(reaction["products"]))
        produced_sets = {tuple(sorted(item["products"])) for item in candidates}
        if target_products in produced_sets:
            loose += 1
        if len(produced_sets) == 1 and target_products in produced_sets:
            single += 1
        # Đúng khi ứng viên ưu tiên cao nhất khớp. Hòa ưu tiên thì ít sản phẩm hơn, rồi thứ tự công thức.
        chosen = primary_candidate(candidates)
        if chosen and tuple(sorted(chosen["products"])) == target_products:
            correct += 1
        elif chosen:
            wrong.append(
                {
                    "id": reaction.get("id"),
                    "condition": condition,
                    "type": reaction.get("type"),
                    "reactants": reaction["reactants"],
                    "expected": reaction["products"],
                    "got": chosen["products"],
                    "rule_id": chosen.get("rule_id"),
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
        "loose": loose,
        "single": single,
        "wrong": len(wrong),
        "missing": len(missing),
        "extra": len(extras),
        "rate": correct / total if total else 0,
        "loose_rate": loose / total if total else 0,
        "single_rate": single / total if total else 0,
        "missing_groups": grouped,
        "wrong_examples": wrong[:12],
        "extras": extras,
    }
