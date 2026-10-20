"""Tìm chuỗi phản ứng ngắn nhất từ chất xuất phát tới chất đích."""

from __future__ import annotations

import heapq
from collections import defaultdict

from app.core.formula import format_equation

# Nước là sản phẩm phụ rất phổ biến. Không dùng nước làm mắt xích trung gian,
# trừ khi nước chính là chất mục tiêu.
_SKIPPED_INTERMEDIATES = {"H2O"}


def condition_penalty(code: str, penalties: dict[str, int]) -> int:
    return int(penalties.get(code, penalties.get("OTHER", 3)))


def build_graph(reactions: list[dict], pool: set[str], penalties: dict[str, int]) -> dict[str, list[dict]]:
    best: dict[tuple[str, str], tuple] = {}
    for reaction in reactions:
        reactants = reaction["reactants"]
        products = reaction["products"]
        for index, main in enumerate(reactants):
            others = [formula for position, formula in enumerate(reactants) if position != index]
            if any(formula not in pool for formula in others):
                continue
            next_products = []
            for product in products:
                if product == main or product in _SKIPPED_INTERMEDIATES:
                    continue
                if product not in next_products:
                    next_products.append(product)
            if not next_products:
                continue
            penalty = condition_penalty(reaction.get("condition") or "NONE", penalties)
            edge_base = {
                "reaction_id": reaction["id"],
                "reactants": reactants,
                "products": products,
                "coefficients": reaction["coefficients"],
                "condition": reaction.get("condition") or "NONE",
                "condition_label": reaction.get("condition_label") or "",
                "condition_symbol": reaction.get("condition_symbol") or "",
                "type": reaction.get("type") or "khac",
                "type_label": reaction.get("type_label") or "",
                "auxiliaries": others,
                "penalty": penalty,
                "aux_count": len(others),
            }
            for product in next_products:
                key = (main, product)
                rank = (penalty, len(others), reaction["id"])
                current = best.get(key)
                if current is not None and current[0] <= rank:
                    continue
                edge = dict(edge_base)
                edge["from"] = main
                edge["to"] = product
                edge["byproducts"] = [item for item in products if item != product]
                best[key] = (rank, edge)

    graph: dict[str, list[dict]] = defaultdict(list)
    for (_main, _product), (_rank, edge) in best.items():
        graph[edge["from"]].append(edge)
    return graph


def water_edges(reactions: list[dict], pool: set[str], penalties: dict[str, int]) -> dict[str, list[dict]]:
    """Cạnh đi tới H2O, chỉ dùng khi chất mục tiêu là nước."""
    graph: dict[str, list[dict]] = defaultdict(list)
    seen = set()
    for reaction in reactions:
        if "H2O" not in reaction["products"]:
            continue
        reactants = reaction["reactants"]
        for index, main in enumerate(reactants):
            if main == "H2O":
                continue
            others = [formula for position, formula in enumerate(reactants) if position != index]
            if any(formula not in pool for formula in others):
                continue
            key = (main, reaction["id"])
            if key in seen:
                continue
            seen.add(key)
            graph[main].append(
                {
                    "reaction_id": reaction["id"],
                    "from": main,
                    "to": "H2O",
                    "reactants": reactants,
                    "products": reaction["products"],
                    "coefficients": reaction["coefficients"],
                    "condition": reaction.get("condition") or "NONE",
                    "condition_label": reaction.get("condition_label") or "",
                    "condition_symbol": reaction.get("condition_symbol") or "",
                    "type": reaction.get("type") or "khac",
                    "type_label": reaction.get("type_label") or "",
                    "auxiliaries": others,
                    "byproducts": [item for item in reaction["products"] if item != "H2O"],
                    "penalty": condition_penalty(reaction.get("condition") or "NONE", penalties),
                    "aux_count": len(others),
                }
            )
    return graph


def find_chain(
    start: str,
    target: str,
    graph: dict[str, list[dict]],
    max_steps: int,
    step_weight: int = 100,
    aux_weight: int = 1,
    extra_graph: dict[str, list[dict]] | None = None,
) -> list[dict] | None:
    if start == target:
        return []
    queue: list[tuple] = [(0, 0, 0, start, [])]
    best = {start: (0, 0, 0)}
    while queue:
        steps, penalty, aux_total, node, path = heapq.heappop(queue)
        if best.get(node) != (steps, penalty, aux_total):
            continue
        if node == target:
            return path
        if steps >= max_steps:
            continue
        visited = {start}
        visited.update(item["to"] for item in path)
        edges = list(graph.get(node, []))
        if target == "H2O" and extra_graph:
            edges.extend(extra_graph.get(node, []))
        for edge in edges:
            nxt = edge["to"]
            if nxt in visited:
                continue
            new_steps = steps + 1
            new_penalty = penalty + edge["penalty"]
            new_aux = aux_total + edge["aux_count"] * aux_weight
            rank = (new_steps, new_penalty, new_aux)
            ranked = (new_steps * step_weight + new_penalty, new_aux, new_steps)
            old = best.get(nxt)
            if old is not None:
                old_ranked = (old[0] * step_weight + old[1], old[2], old[0])
                if old_ranked <= ranked:
                    continue
            best[nxt] = rank
            heapq.heappush(queue, (new_steps, new_penalty, new_aux, nxt, path + [edge]))
    return None


def edge_equation(edge: dict) -> str:
    symbol = edge.get("condition_symbol") or ""
    if edge.get("condition") in (None, "", "NONE"):
        symbol = ""
    return format_equation(edge["reactants"], edge["products"], edge["coefficients"], symbol or None)
