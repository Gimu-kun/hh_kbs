"""Bộ suy diễn cho cân bằng, chuỗi phản ứng và bài toán đại lượng."""

from __future__ import annotations

from fractions import Fraction

from app.core.balancer import BalanceError, balance_formulas
from app.core.chain_search import build_graph, edge_equation, find_chain, water_edges
from app.core.constants import MOLAR_VOLUME_STP
from app.core.formula import EquationError, parse_equation, parse_formula
from app.core.forward import _kind_class, generate_pool_reactions
from app.core.numbers import format_number, to_fraction
from app.core.renderer import TemplateError, join_explanation, render_balance, render_chain, render_quantity
from app.core.species import Catalog
from app.core.stoichiometry import QuantityError, solve_quantity
from app.services.auth import configure as configure_auth
from app.services.errors import KnowledgeError
from app.services.knowledge_base import KnowledgeBase
from app.services.reviews import ReviewStore


class InferenceEngine:
    def __init__(self, knowledge: KnowledgeBase):
        self.knowledge = knowledge
        self.reviews = ReviewStore(knowledge.data_dir)
        configure_auth(knowledge.data_dir)
        self._catalog_cache: Catalog | None = None
        self._pool_key: frozenset | None = None
        self._pool_reactions: list[dict] | None = None

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

        penalties, step_weight, aux_weight, h2_weight, pattern = self._search_weights()
        reactions = self._generated_reactions()
        pool = {item["formula"] for item in self.knowledge.reagents.list()}
        catalog = self._catalog()

        def class_of(formula: str) -> str:
            species = catalog.get(formula)
            return _kind_class(species) if species else ""

        graph = build_graph(reactions, pool, penalties, class_of)
        extra = water_edges(reactions, pool, penalties, class_of) if target == "H2O" else None
        path = find_chain(
            start,
            target,
            graph,
            max_steps,
            step_weight,
            aux_weight,
            extra,
            h2_weight,
            pattern,
            class_of(target),
        )

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

        detailed = []
        for index, edge in enumerate(path, start=1):
            condition_label = edge.get("condition_label") or "không cần điều kiện"
            if edge.get("condition") in (None, "", "NONE"):
                condition_label = "không cần điều kiện"
            review = self.reviews.classify_step(edge, source="solution")
            review_status = review.get("status") or "unknown"
            detailed.append(
                {
                    "index": index,
                    "reaction_id": edge["reaction_id"],
                    "from": edge["from"],
                    "to": edge["to"],
                    "equation": edge_equation(edge),
                    "reactants": edge["reactants"],
                    "products": edge["products"],
                    "coefficients": edge["coefficients"],
                    "condition": edge.get("condition"),
                    "condition_label": condition_label,
                    "type": edge.get("type"),
                    "type_label": edge.get("type_label") or "Phản ứng",
                    "auxiliaries": edge.get("auxiliaries") or [],
                    "byproducts": edge.get("byproducts") or [],
                    "rule_id": edge.get("rule_id"),
                    "rule_text": edge.get("rule_text") or "",
                    "review_status": review_status,
                    "review_id": review.get("id"),
                    "pending": review_status == "pending",
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

    def invalidate_generation(self) -> None:
        self._pool_key = None
        self._pool_reactions = None

    def _catalog(self) -> Catalog:
        if self._catalog_cache is None:
            series = []
            for heuristic in self.knowledge.heuristics.list():
                if heuristic.get("kind") == "activity_series":
                    series = list(heuristic.get("series") or [])
            self._catalog_cache = Catalog(
                self.knowledge.compounds.list(),
                self.knowledge.elements.list(),
                series,
            )
        return self._catalog_cache

    def _generated_reactions(self) -> list[dict]:
        rejected = self.reviews.rejected_signatures()
        key = frozenset(rejected)
        if self._pool_reactions is not None and self._pool_key == key:
            return self._pool_reactions
        pool = {item["formula"] for item in self.knowledge.reagents.list()}
        generated = generate_pool_reactions(self._catalog(), self.knowledge.rules.list(), pool, rejected)
        conditions = self.knowledge.condition_map()
        for item in generated:
            condition = conditions.get(item.get("condition") or "NONE")
            if condition:
                item["condition_label"] = condition["name"]
                item["condition_symbol"] = condition.get("symbol") or ""
        self._pool_key = key
        self._pool_reactions = generated
        return generated

    def _search_weights(self) -> tuple[dict[str, int], int, int, int, list[str]]:
        penalties = {"NONE": 0, "OTHER": 3}
        for condition in self.knowledge.conditions.list():
            penalties[condition["code"]] = int(condition.get("complexity") or 0)
        step_weight = 100
        aux_weight = 1
        h2_weight = 1
        pattern: list[str] = []
        for heuristic in self.knowledge.heuristics.list():
            if heuristic.get("kind") == "min_steps":
                step_weight = int(heuristic.get("weight") or step_weight)
            elif heuristic.get("kind") == "aux_penalty":
                aux_weight = int(heuristic.get("weight") or aux_weight)
            elif heuristic.get("kind") == "condition_penalty":
                h2_weight = int(heuristic.get("weight") or h2_weight)
                for code, value in (heuristic.get("penalties") or {}).items():
                    penalties[code] = int(value)
            elif heuristic.get("kind") == "pattern":
                pattern = list(heuristic.get("pattern") or [])
        return penalties, step_weight, aux_weight, h2_weight, pattern

    def _molar_volume(self) -> Fraction:
        record = self.knowledge.formulas.get("F_VM")
        if record and record.get("value") is not None:
            return to_fraction(record["value"])
        return to_fraction(MOLAR_VOLUME_STP)


def _json_number(value: Fraction):
    if value.denominator == 1:
        return value.numerator
    return float(value)
