"""Bộ suy diễn cho cân bằng, chuỗi phản ứng và bài toán đại lượng."""

from __future__ import annotations

from fractions import Fraction

from app.core.balancer import BalanceError, balance_formulas
from app.core.chain_search import build_graph, edge_equation, find_chain, water_edges
from app.core.constants import MOLAR_VOLUME_STP
from app.core.formula import EquationError, parse_equation, parse_formula
from app.core.numbers import format_number, to_fraction
from app.core.renderer import TemplateError, join_explanation, render_balance, render_chain, render_quantity
from app.core.rules_match import match_rule
from app.core.stoichiometry import QuantityError, solve_quantity
from app.services.errors import KnowledgeError
from app.services.knowledge_base import KnowledgeBase


class InferenceEngine:
    def __init__(self, knowledge: KnowledgeBase):
        self.knowledge = knowledge

    def balance(self, equation: str) -> dict:
        try:
            reactants, products = parse_equation(equation)
            result = balance_formulas(reactants, products)
            steps = render_balance(result, self.knowledge.template_map())
        except (EquationError, BalanceError, TemplateError) as error:
            raise KnowledgeError(str(error))
        return {
            "problem": "balance",
            "input": equation,
            "reactants": result["reactants"],
            "products": result["products"],
            "coefficients": result["coefficients"],
            "balanced": result["balanced"],
            "steps": steps,
            "explanation": join_explanation(steps),
        }

    def chain(self, start: str, target: str, max_steps: int = 6) -> dict:
        compounds = self.knowledge.compound_map()
        start = self.knowledge.resolve_formula(start.strip(), compounds, "Chất xuất phát")
        target = self.knowledge.resolve_formula(target.strip(), compounds, "Chất mục tiêu")
        if max_steps < 1 or max_steps > 12:
            raise KnowledgeError("Số bước tối đa phải từ 1 đến 12.")

        penalties, step_weight, aux_weight = self._search_weights()
        reactions = self._decorate_reactions()
        pool = {item["formula"] for item in self.knowledge.reagents.list()}
        # Chất xuất phát luôn được dùng, không cần nằm trong kho thuốc thử.
        graph = build_graph(reactions, pool, penalties)
        extra = water_edges(reactions, pool, penalties) if target == "H2O" else None
        path = find_chain(start, target, graph, max_steps, step_weight, aux_weight, extra)

        if path is None:
            rendered = {
                "found": False,
                "same": False,
                "start": start,
                "target": target,
                "max_steps": max_steps,
            }
            steps = render_chain(rendered, self.knowledge.template_map())
            return {
                "problem": "chain",
                "found": False,
                "start": start,
                "target": target,
                "reactions": [],
                "answer": "",
                "steps": steps,
                "explanation": join_explanation(steps),
            }

        if path == []:
            rendered = {"found": True, "same": True, "start": start, "target": target}
            steps = render_chain(rendered, self.knowledge.template_map())
            return {
                "problem": "chain",
                "found": True,
                "start": start,
                "target": target,
                "reactions": [],
                "answer": start,
                "steps": steps,
                "explanation": join_explanation(steps),
            }

        rules = self.knowledge.rules.list()
        elements = self.knowledge.element_map()
        detailed = []
        for index, edge in enumerate(path, start=1):
            rule = match_rule(edge["from"], edge, compounds, elements, rules)
            condition_label = edge.get("condition_label") or "không cần điều kiện"
            if edge.get("condition") in (None, "", "NONE"):
                condition_label = "không cần điều kiện"
            detailed.append(
                {
                    "index": index,
                    "reaction_id": edge["reaction_id"],
                    "from": edge["from"],
                    "to": edge["to"],
                    "equation": edge_equation(edge),
                    "condition": edge.get("condition"),
                    "condition_label": condition_label,
                    "type": edge.get("type"),
                    "type_label": edge.get("type_label") or "Phản ứng",
                    "auxiliaries": edge.get("auxiliaries") or [],
                    "byproducts": edge.get("byproducts") or [],
                    "rule_id": rule["id"] if rule else None,
                    "rule_text": f"{rule['if_text']} → {rule['then_text']}" if rule else "",
                }
            )
        rendered = {
            "found": True,
            "same": False,
            "start": start,
            "target": target,
            "reactions": detailed,
        }
        steps = render_chain(rendered, self.knowledge.template_map())
        listing = "\n".join(f"({item['index']}) {item['equation']}" for item in detailed)
        return {
            "problem": "chain",
            "found": True,
            "start": start,
            "target": target,
            "reactions": detailed,
            "answer": listing,
            "steps": steps,
            "explanation": join_explanation(steps),
        }

    def quantity(self, payload: dict) -> dict:
        equation = str(payload.get("equation") or "")
        known = payload.get("known") or {}
        find = payload.get("find") or {}
        try:
            reactants, products = parse_equation(equation)
            balanced = balance_formulas(reactants, products)
        except (EquationError, BalanceError) as error:
            raise KnowledgeError(str(error))

        known_formula = str(known.get("formula") or "").strip()
        find_formula = str(find.get("formula") or "").strip()
        known_kind = str(known.get("kind") or "")
        find_kind = str(find.get("kind") or "")
        try:
            known_value = to_fraction(known.get("value"))
        except Exception as error:
            raise KnowledgeError("Giá trị đại lượng đã biết không phải số.") from error

        compositions = {}
        for formula in reactants + products:
            compositions[formula] = parse_formula(formula)
        molar_volume = self._molar_volume()
        try:
            solved = solve_quantity(
                reactants,
                products,
                balanced["coefficients"],
                known_formula,
                known_kind,
                known_value,
                find_formula,
                find_kind,
                compositions,
                self.knowledge.element_map(),
                self.knowledge.compound_map(),
                molar_volume,
            )
            balance_steps = render_balance(balanced, self.knowledge.template_map())
            quantity_view = {
                **solved,
                "known_formula": known_formula,
                "find_formula": find_formula,
                "known_kind": known_kind,
                "find_kind": find_kind,
                "known_value": known_value,
            }
            steps = render_quantity(balance_steps, quantity_view, self.knowledge.template_map())
        except (QuantityError, TemplateError) as error:
            raise KnowledgeError(str(error))

        return {
            "problem": "quantity",
            "input": equation,
            "balanced": balanced["balanced"],
            "known": {
                "formula": known_formula,
                "kind": known_kind,
                "value": _json_number(known_value),
                "moles": _json_number(solved["moles_known"]),
                "molar_mass": _json_number(solved["molar_mass_known"]),
            },
            "find": {
                "formula": find_formula,
                "kind": find_kind,
                "value": _json_number(solved["value"]),
                "unit": solved["unit"],
                "display": f"{format_number(solved['value'])} {solved['unit']}",
                "moles": _json_number(solved["moles_find"]),
                "molar_mass": _json_number(solved["molar_mass_find"]),
            },
            "steps": steps,
            "explanation": join_explanation(steps),
        }

    def _decorate_reactions(self) -> list[dict]:
        conditions = self.knowledge.condition_map()
        decorated = []
        for reaction in self.knowledge.reactions.list():
            item = dict(reaction)
            condition = conditions.get(item.get("condition") or "NONE")
            if condition:
                item["condition_label"] = condition["name"]
                item["condition_symbol"] = condition.get("symbol") or ""
            decorated.append(item)
        return decorated

    def _search_weights(self) -> tuple[dict[str, int], int, int]:
        penalties = {"NONE": 0, "OTHER": 3}
        for condition in self.knowledge.conditions.list():
            penalties[condition["code"]] = int(condition.get("complexity") or 0)
        step_weight = 100
        aux_weight = 1
        for heuristic in self.knowledge.heuristics.list():
            if heuristic.get("kind") == "min_steps":
                step_weight = int(heuristic.get("weight") or step_weight)
            elif heuristic.get("kind") == "aux_penalty":
                aux_weight = int(heuristic.get("weight") or aux_weight)
            elif heuristic.get("kind") == "condition_penalty":
                for code, value in (heuristic.get("penalties") or {}).items():
                    penalties[code] = int(value)
        return penalties, step_weight, aux_weight

    def _molar_volume(self) -> Fraction:
        record = self.knowledge.formulas.get("F_VM")
        if record and record.get("value") is not None:
            return to_fraction(record["value"])
        return to_fraction(MOLAR_VOLUME_STP)


def _json_number(value: Fraction):
    if value.denominator == 1:
        return value.numerator
    return float(value)
