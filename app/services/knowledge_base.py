"""Kiểm tra nhất quán và thao tác CRUD trên các thành phần của mô hình."""

from __future__ import annotations

from pathlib import Path

from app.core.balancer import BalanceError, balance_formulas
from app.core.constants import (
    ACTIVITY_SERIES,
    ALKALI_METALS,
    ALKALINE_EARTH,
    CLASS_LABELS,
    CLASS_ONTOLOGY,
    COMPOUND_CLASSES,
    ELEMENT_TYPE_LABELS,
    ELEMENT_TYPES,
    REACTION_TYPE_LABELS,
    REACTION_TYPES,
    SOLUBILITIES,
    SOLUBILITY_LABELS,
    STATE_LABELS,
    STATES,
)
from app.core.formula import FormulaError, parse_formula
from app.core.numbers import to_fraction
from app.repositories.json_store import JsonStore
from app.services.errors import KnowledgeError


class KnowledgeBase:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.elements = JsonStore(data_dir / "elements.json", "symbol")
        self.compounds = JsonStore(data_dir / "compounds.json", "formula")
        self.reactions = JsonStore(data_dir / "reactions.json", "id")
        self.rules = JsonStore(data_dir / "rules.json", "id")
        self.conditions = JsonStore(data_dir / "conditions.json", "code")
        self.heuristics = JsonStore(data_dir / "heuristics.json", "id")
        self.formulas = JsonStore(data_dir / "formulas.json", "id")
        self.reagents = JsonStore(data_dir / "reagents.json", "formula")
        self.templates = JsonStore(data_dir / "templates.json", "id")

    def summary(self) -> dict:
        return {
            "model": "K = (E, C, R, L, Cond, H), bổ sung F (công thức tính), Reagent (kho thuốc thử), Template (mẫu diễn giải)",
            "counts": {
                "elements": len(self.elements.list()),
                "compounds": len(self.compounds.list()),
                "reactions": len(self.reactions.list()),
                "rules": len(self.rules.list()),
                "conditions": len(self.conditions.list()),
                "heuristics": len(self.heuristics.list()),
                "formulas": len(self.formulas.list()),
                "reagents": len(self.reagents.list()),
                "templates": len(self.templates.list()),
            },
            "activity_series": ACTIVITY_SERIES,
        }

    def template_map(self) -> dict[str, str]:
        return {item["id"]: item["content"] for item in self.templates.list()}

    def element_map(self) -> dict[str, dict]:
        return {item["symbol"]: item for item in self.elements.list()}

    def compound_map(self) -> dict[str, dict]:
        return {item["formula"]: item for item in self.compounds.list()}

    def condition_map(self) -> dict[str, dict]:
        return {item["code"]: item for item in self.conditions.list()}

    def resolve_formula(self, formula: str, store: dict[str, dict], label: str) -> str:
        if formula in store:
            return formula
        folded = {key.lower(): key for key in store}
        found = folded.get(formula.lower())
        if found:
            return found
        raise KnowledgeError(f"{label} '{formula}' không có trong cơ sở tri thức.", 404)

    # --- Nguyên tố ---
    def create_element(self, payload: dict) -> dict:
        item = self._normalize_element(payload)
        if self.elements.exists(item["symbol"]):
            raise KnowledgeError(f"Nguyên tố {item['symbol']} đã tồn tại.", 409)
        return self.elements.create(item)

    def update_element(self, symbol: str, payload: dict) -> dict:
        current = self.elements.get(symbol)
        if current is None:
            raise KnowledgeError(f"Không tìm thấy nguyên tố {symbol}.", 404)
        item = self._normalize_element(payload)
        if item["symbol"] != symbol:
            raise KnowledgeError("Không đổi ký hiệu nguyên tố khi sửa. Hãy xóa rồi tạo mới.")
        self._recalculate_compound_masses(item)
        return self.elements.replace(symbol, item)

    def delete_element(self, symbol: str) -> dict:
        if self.elements.get(symbol) is None:
            raise KnowledgeError(f"Không tìm thấy nguyên tố {symbol}.", 404)
        used = [
            compound["formula"]
            for compound in self.compounds.list()
            if symbol in (compound.get("composition") or {})
        ]
        if used:
            sample = ", ".join(used[:8])
            raise KnowledgeError(f"Không xóa được {symbol} vì còn chất sử dụng: {sample}.", 409)
        return self.elements.delete(symbol)

    def _normalize_element(self, payload: dict) -> dict:
        symbol = str(payload.get("symbol") or "").strip()
        if not symbol or not symbol[0].isupper():
            raise KnowledgeError("Ký hiệu nguyên tố phải bắt đầu bằng chữ in hoa.")
        name = str(payload.get("name") or "").strip()
        if not name:
            raise KnowledgeError("Thiếu tên nguyên tố.")
        try:
            atomic_number = int(payload.get("z"))
            mass = float(payload.get("mass"))
        except (TypeError, ValueError):
            raise KnowledgeError("Số hiệu nguyên tử và nguyên tử khối phải là số.")
        if atomic_number <= 0 or mass <= 0:
            raise KnowledgeError("Số hiệu nguyên tử và nguyên tử khối phải lớn hơn 0.")
        element_type = payload.get("type")
        if element_type not in ELEMENT_TYPES:
            raise KnowledgeError(f"Loại nguyên tố phải thuộc {', '.join(ELEMENT_TYPES)}.")
        valence = payload.get("valence") or []
        if not isinstance(valence, list) or any(not isinstance(item, int) for item in valence):
            raise KnowledgeError("Hóa trị phải là danh sách số nguyên.")
        activity = payload.get("activity")
        if activity is not None:
            try:
                activity = int(activity)
            except (TypeError, ValueError):
                raise KnowledgeError("Activity phải là số nguyên hoặc null.")
            if activity <= 0:
                raise KnowledgeError("Activity phải lớn hơn 0. Số càng nhỏ thì hoạt động càng mạnh.")
        groups = list(payload.get("groups") or [])
        if symbol in ALKALI_METALS and "kiem" not in groups:
            groups.append("kiem")
        if symbol in ALKALINE_EARTH and "kiem_tho" not in groups:
            groups.append("kiem_tho")
        mass_value = int(mass) if mass.is_integer() else mass
        return {
            "symbol": symbol,
            "name": name,
            "z": atomic_number,
            "mass": mass_value,
            "valence": valence,
            "type": element_type,
            "type_label": ELEMENT_TYPE_LABELS[element_type],
            "activity": activity,
            "groups": groups,
        }

    def _recalculate_compound_masses(self, element: dict) -> None:
        elements = self.element_map()
        elements[element["symbol"]] = element
        for compound in self.compounds.list():
            composition = compound.get("composition") or {}
            if element["symbol"] not in composition:
                continue
            compound["molar_mass"] = _molar_mass_number(composition, elements)
            self.compounds.replace(compound["formula"], compound)

    # --- Chất ---
    def create_compound(self, payload: dict) -> dict:
        item = self._normalize_compound(payload)
        if self.compounds.exists(item["formula"]):
            raise KnowledgeError(f"Chất {item['formula']} đã tồn tại.", 409)
        return self.compounds.create(item)

    def update_compound(self, formula: str, payload: dict) -> dict:
        if self.compounds.get(formula) is None:
            raise KnowledgeError(f"Không tìm thấy chất {formula}.", 404)
        item = self._normalize_compound(payload)
        if item["formula"] != formula:
            raise KnowledgeError("Không đổi công thức khi sửa chất. Hãy xóa rồi tạo mới.")
        return self.compounds.replace(formula, item)

    def delete_compound(self, formula: str) -> dict:
        if self.compounds.get(formula) is None:
            raise KnowledgeError(f"Không tìm thấy chất {formula}.", 404)
        used = [
            reaction["id"]
            for reaction in self.reactions.list()
            if formula in reaction["reactants"] or formula in reaction["products"]
        ]
        if used:
            raise KnowledgeError(f"Không xóa được {formula} vì còn phản ứng: {', '.join(used[:8])}.", 409)
        if self.reagents.exists(formula):
            raise KnowledgeError(f"Không xóa được {formula} vì chất này đang nằm trong kho thuốc thử.", 409)
        return self.compounds.delete(formula)

    def _normalize_compound(self, payload: dict) -> dict:
        formula = str(payload.get("formula") or "").strip()
        try:
            composition = parse_formula(formula)
        except FormulaError as error:
            raise KnowledgeError(str(error))
        supplied = payload.get("composition")
        if supplied is not None and dict(supplied) != composition:
            raise KnowledgeError(
                f"Thành phần nguyên tố không khớp công thức {formula}. Hệ thống phân tích được {composition}."
            )
        elements = self.element_map()
        missing = [symbol for symbol in composition if symbol not in elements]
        if missing:
            raise KnowledgeError(f"Công thức {formula} chứa nguyên tố chưa có trong tập E: {', '.join(missing)}.")
        name = str(payload.get("name") or formula).strip()
        compound_class = payload.get("class")
        if compound_class not in COMPOUND_CLASSES:
            raise KnowledgeError(f"Loại chất phải thuộc: {', '.join(COMPOUND_CLASSES)}.")
        state = payload.get("state")
        if state not in STATES:
            raise KnowledgeError(f"Trạng thái phải thuộc: {', '.join(STATES)}.")
        soluble = payload.get("soluble")
        if soluble not in SOLUBILITIES:
            raise KnowledgeError(f"Tính tan phải thuộc: {', '.join(SOLUBILITIES)}.")
        try:
            charge = int(payload.get("charge") if payload.get("charge") is not None else 0)
        except (TypeError, ValueError):
            raise KnowledgeError("Điện tích phải là số nguyên.")
        return {
            "formula": formula,
            "name": name,
            "class": compound_class,
            "class_label": CLASS_LABELS[compound_class],
            "ontology": CLASS_ONTOLOGY[compound_class],
            "composition": composition,
            "state": state,
            "state_label": STATE_LABELS[state],
            "soluble": soluble,
            "soluble_label": SOLUBILITY_LABELS[soluble],
            "charge": charge,
            "molar_mass": _molar_mass_number(composition, elements),
        }

    # --- Phản ứng ---
    def create_reaction(self, payload: dict) -> dict:
        item = self._normalize_reaction(payload, new=True)
        if self.reactions.exists(item["id"]):
            raise KnowledgeError(f"Phản ứng {item['id']} đã tồn tại.", 409)
        return self.reactions.create(item)

    def update_reaction(self, reaction_id: str, payload: dict) -> dict:
        if self.reactions.get(reaction_id) is None:
            raise KnowledgeError(f"Không tìm thấy phản ứng {reaction_id}.", 404)
        item = self._normalize_reaction(payload, new=False)
        if item["id"] != reaction_id:
            raise KnowledgeError("Không đổi mã phản ứng khi sửa.")
        return self.reactions.replace(reaction_id, item)

    def delete_reaction(self, reaction_id: str) -> dict:
        item = self.reactions.delete(reaction_id)
        if item is None:
            raise KnowledgeError(f"Không tìm thấy phản ứng {reaction_id}.", 404)
        return item

    def _next_reaction_id(self) -> str:
        highest = 0
        for reaction in self.reactions.list():
            text = reaction["id"]
            if text.startswith("R") and text[1:].isdigit():
                highest = max(highest, int(text[1:]))
        return f"R{highest + 1:03d}"

    def _normalize_reaction(self, payload: dict, new: bool) -> dict:
        reaction_id = str(payload.get("id") or "").strip()
        if not reaction_id:
            if not new:
                raise KnowledgeError("Thiếu mã phản ứng.")
            reaction_id = self._next_reaction_id()
        reactants = [str(item).strip() for item in payload.get("reactants") or []]
        products = [str(item).strip() for item in payload.get("products") or []]
        if not reactants or not products:
            raise KnowledgeError("Phản ứng cần có chất tham gia và sản phẩm.")
        compounds = self.compound_map()
        missing = [formula for formula in reactants + products if formula not in compounds]
        if missing:
            raise KnowledgeError(f"Các chất chưa có trong tập C: {', '.join(missing)}.")
        coefficients = payload.get("coefficients")
        if coefficients is None:
            try:
                balanced = balance_formulas(reactants, products)
            except BalanceError as error:
                raise KnowledgeError(str(error))
            coefficients = balanced["coefficients"]
        if len(coefficients) != len(reactants) + len(products):
            raise KnowledgeError("Số hệ số phải bằng tổng số chất tham gia và sản phẩm.")
        if any(not isinstance(value, int) or value <= 0 for value in coefficients):
            raise KnowledgeError("Hệ số phải là số nguyên dương.")
        try:
            balanced = balance_formulas(reactants, products)
        except BalanceError as error:
            raise KnowledgeError(str(error))
        if coefficients != balanced["coefficients"]:
            expected = ", ".join(str(value) for value in balanced["coefficients"])
            raise KnowledgeError(
                f"Bộ hệ số chưa là bộ nguyên dương tối giản bảo toàn nguyên tố. Bộ đúng: {expected}."
            )
        condition = payload.get("condition") or "NONE"
        if self.conditions.get(condition) is None:
            raise KnowledgeError(f"Điều kiện '{condition}' không có trong tập Cond.")
        reaction_type = payload.get("type") or "khac"
        if reaction_type not in REACTION_TYPES:
            raise KnowledgeError(f"Loại phản ứng phải thuộc: {', '.join(REACTION_TYPES)}.")
        return {
            "id": reaction_id,
            "reactants": reactants,
            "products": products,
            "coefficients": coefficients,
            "condition": condition,
            "condition_label": self.conditions.get(condition)["name"],
            "condition_symbol": self.conditions.get(condition).get("symbol") or "",
            "type": reaction_type,
            "type_label": REACTION_TYPE_LABELS[reaction_type],
            "condition_raw": payload.get("condition_raw") or "",
            "source": payload.get("source") or "manual",
        }

    # --- Luật, điều kiện, heuristic, công thức, thuốc thử, template ---
    def create_rule(self, payload: dict) -> dict:
        item = self._require_id(payload, "id", "luật")
        self._require_text(item, "if_text", "then_text")
        if self.rules.exists(item["id"]):
            raise KnowledgeError(f"Luật {item['id']} đã tồn tại.", 409)
        item.setdefault("group", "")
        item.setdefault("type", "khac")
        item.setdefault("priority", 1)
        item.setdefault("match", {})
        return self.rules.create(item)

    def update_rule(self, rule_id: str, payload: dict) -> dict:
        if self.rules.get(rule_id) is None:
            raise KnowledgeError(f"Không tìm thấy luật {rule_id}.", 404)
        item = self._require_id(payload, "id", "luật")
        if item["id"] != rule_id:
            raise KnowledgeError("Không đổi mã luật khi sửa.")
        self._require_text(item, "if_text", "then_text")
        item.setdefault("match", {})
        return self.rules.replace(rule_id, item)

    def delete_rule(self, rule_id: str) -> dict:
        item = self.rules.delete(rule_id)
        if item is None:
            raise KnowledgeError(f"Không tìm thấy luật {rule_id}.", 404)
        return item

    def create_condition(self, payload: dict) -> dict:
        item = self._normalize_condition(payload)
        if self.conditions.exists(item["code"]):
            raise KnowledgeError(f"Điều kiện {item['code']} đã tồn tại.", 409)
        return self.conditions.create(item)

    def update_condition(self, code: str, payload: dict) -> dict:
        if self.conditions.get(code) is None:
            raise KnowledgeError(f"Không tìm thấy điều kiện {code}.", 404)
        item = self._normalize_condition(payload)
        if item["code"] != code:
            raise KnowledgeError("Không đổi mã điều kiện khi sửa.")
        saved = self.conditions.replace(code, item)
        for reaction in self.reactions.list():
            if reaction["condition"] == code:
                reaction["condition_label"] = item["name"]
                reaction["condition_symbol"] = item.get("symbol") or ""
                self.reactions.replace(reaction["id"], reaction)
        return saved

    def delete_condition(self, code: str) -> dict:
        if self.conditions.get(code) is None:
            raise KnowledgeError(f"Không tìm thấy điều kiện {code}.", 404)
        used = [reaction["id"] for reaction in self.reactions.list() if reaction["condition"] == code]
        if used:
            raise KnowledgeError(f"Không xóa được điều kiện {code} vì còn phản ứng: {', '.join(used[:8])}.", 409)
        return self.conditions.delete(code)

    def _normalize_condition(self, payload: dict) -> dict:
        code = str(payload.get("code") or "").strip()
        name = str(payload.get("name") or "").strip()
        if not code or not name:
            raise KnowledgeError("Điều kiện cần có mã và tên.")
        try:
            complexity = int(payload.get("complexity") if payload.get("complexity") is not None else 1)
        except (TypeError, ValueError):
            raise KnowledgeError("Độ phức tạp của điều kiện phải là số nguyên.")
        return {
            "code": code,
            "name": name,
            "symbol": str(payload.get("symbol") or ""),
            "complexity": complexity,
            "description": str(payload.get("description") or ""),
        }

    def create_heuristic(self, payload: dict) -> dict:
        item = self._require_id(payload, "id", "heuristic")
        if self.heuristics.exists(item["id"]):
            raise KnowledgeError(f"Heuristic {item['id']} đã tồn tại.", 409)
        if "name" not in item or "kind" not in item:
            raise KnowledgeError("Heuristic cần có name và kind.")
        return self.heuristics.create(item)

    def update_heuristic(self, heuristic_id: str, payload: dict) -> dict:
        if self.heuristics.get(heuristic_id) is None:
            raise KnowledgeError(f"Không tìm thấy heuristic {heuristic_id}.", 404)
        item = self._require_id(payload, "id", "heuristic")
        if item["id"] != heuristic_id:
            raise KnowledgeError("Không đổi mã heuristic khi sửa.")
        return self.heuristics.replace(heuristic_id, item)

    def delete_heuristic(self, heuristic_id: str) -> dict:
        item = self.heuristics.delete(heuristic_id)
        if item is None:
            raise KnowledgeError(f"Không tìm thấy heuristic {heuristic_id}.", 404)
        return item

    def create_formula(self, payload: dict) -> dict:
        item = self._require_id(payload, "id", "công thức")
        if self.formulas.exists(item["id"]):
            raise KnowledgeError(f"Công thức {item['id']} đã tồn tại.", 409)
        self._require_text(item, "expression", "description")
        return self.formulas.create(item)

    def update_formula(self, formula_id: str, payload: dict) -> dict:
        if self.formulas.get(formula_id) is None:
            raise KnowledgeError(f"Không tìm thấy công thức {formula_id}.", 404)
        item = self._require_id(payload, "id", "công thức")
        if item["id"] != formula_id:
            raise KnowledgeError("Không đổi mã công thức khi sửa.")
        return self.formulas.replace(formula_id, item)

    def delete_formula(self, formula_id: str) -> dict:
        item = self.formulas.delete(formula_id)
        if item is None:
            raise KnowledgeError(f"Không tìm thấy công thức {formula_id}.", 404)
        return item

    def create_reagent(self, payload: dict) -> dict:
        formula = str(payload.get("formula") or "").strip()
        if self.compounds.get(formula) is None:
            raise KnowledgeError(f"Thuốc thử {formula} phải là chất đã có trong tập C.")
        if self.reagents.exists(formula):
            raise KnowledgeError(f"Thuốc thử {formula} đã có trong kho.", 409)
        return self.reagents.create(
            {
                "formula": formula,
                "group": str(payload.get("group") or ""),
                "note": str(payload.get("note") or ""),
            }
        )

    def update_reagent(self, formula: str, payload: dict) -> dict:
        if self.reagents.get(formula) is None:
            raise KnowledgeError(f"Không tìm thấy thuốc thử {formula}.", 404)
        body_formula = str(payload.get("formula") or formula).strip()
        if body_formula != formula:
            raise KnowledgeError("Không đổi công thức thuốc thử khi sửa.")
        if self.compounds.get(formula) is None:
            raise KnowledgeError(f"Thuốc thử {formula} phải là chất đã có trong tập C.")
        return self.reagents.replace(
            formula,
            {"formula": formula, "group": str(payload.get("group") or ""), "note": str(payload.get("note") or "")},
        )

    def delete_reagent(self, formula: str) -> dict:
        item = self.reagents.delete(formula)
        if item is None:
            raise KnowledgeError(f"Không tìm thấy thuốc thử {formula}.", 404)
        return item

    def create_template(self, payload: dict) -> dict:
        item = self._require_id(payload, "id", "template")
        if self.templates.exists(item["id"]):
            raise KnowledgeError(f"Template {item['id']} đã tồn tại.", 409)
        if "content" not in item:
            raise KnowledgeError("Template cần có content.")
        item.setdefault("problem", "general")
        item.setdefault("description", "")
        return self.templates.create(item)

    def update_template(self, template_id: str, payload: dict) -> dict:
        if self.templates.get(template_id) is None:
            raise KnowledgeError(f"Không tìm thấy template {template_id}.", 404)
        item = self._require_id(payload, "id", "template")
        if item["id"] != template_id:
            raise KnowledgeError("Không đổi mã template khi sửa.")
        if "content" not in item:
            raise KnowledgeError("Template cần có content.")
        return self.templates.replace(template_id, item)

    def delete_template(self, template_id: str) -> dict:
        item = self.templates.delete(template_id)
        if item is None:
            raise KnowledgeError(f"Không tìm thấy template {template_id}.", 404)
        return item

    def _require_id(self, payload: dict, field: str, label: str) -> dict:
        item = dict(payload)
        if not str(item.get(field) or "").strip():
            raise KnowledgeError(f"Thiếu mã {label}.")
        item[field] = str(item[field]).strip()
        return item

    def _require_text(self, item: dict, *fields: str) -> None:
        for field in fields:
            if not str(item.get(field) or "").strip():
                raise KnowledgeError(f"Thiếu nội dung '{field}'.")


def _molar_mass_number(composition: dict, elements: dict) -> float | int:
    total = to_fraction(0)
    for symbol, count in composition.items():
        total += to_fraction(elements[symbol]["mass"]) * count
    if total.denominator == 1:
        return total.numerator
    return float(total)
