"""Sinh các phản ứng cụ thể từ luật R2. Không lưu sẵn đường đi của bài toán."""

from __future__ import annotations

from dataclasses import dataclass
from math import gcd

from cstt.chem import balance, format_equation, solubility_rule
from cstt.kb import KnowledgeBase


@dataclass(frozen=True)
class Reaction:
    rule_id: str
    rule_name: str
    reactants: tuple[tuple[str, int], ...]
    products: tuple[tuple[str, int], ...]
    conditions: tuple[str, ...]
    explain: str

    def text(self, kb: KnowledgeBase) -> str:
        return format_equation(self.reactants, self.products, condition_text(kb, self.conditions))


def condition_text(kb: KnowledgeBase, codes: tuple[str, ...] | list[str]) -> str:
    index = {item["code"]: item for item in kb.conditions["items"]}
    labels = []
    for code in codes:
        item = index.get(code)
        if item is None:
            raise ValueError(f"Không có điều kiện {code}.")
        if item["symbol"]:
            labels.append(item["symbol"])
    return ", ".join(labels)


def _salt(kb: KnowledgeBase, cation: str, anion: str, valence: int):
    anion_charge = abs(next(item["charge"] for item in kb.r1["anions"] if item["formula"] == anion))
    divisor = gcd(valence, anion_charge)
    cation_count = anion_charge // divisor
    anion_count = valence // divisor
    for compound in kb.compounds.values():
        ions = compound.ions
        if not ions or compound.class_id == "axit":
            continue
        if (
            ions["cation"] == cation
            and ions["anion"]["formula"] == anion
            and ions["cation_count"] == cation_count
            and ions["anion_count"] == anion_count
        ):
            return compound
    return None


def _hydroxide(kb: KnowledgeBase, cation: str, valence: int):
    return _salt(kb, cation, "OH", valence)


def _oxide_of(kb: KnowledgeBase, metal: str, valence: int) -> str | None:
    divisor = gcd(valence, 2)
    metal_count = 2 // divisor
    oxygen_count = valence // divisor
    for compound in kb.compounds.values():
        if compound.comp.get(metal) == metal_count and compound.comp.get("O") == oxygen_count:
            if set(compound.comp) == {metal, "O"}:
                return compound.formula
    return None


def _build(kb: KnowledgeBase, rule: dict, rule_id: str, reactants: list[str], products: list[str], conditions: list[str], explain: str) -> Reaction | None:
    if any(formula not in kb.compounds for formula in reactants + products):
        return None
    if set(reactants) & set(products):
        return None
    compositions = {formula: kb.compounds[formula].comp for formula in reactants + products}
    coefficients = balance(reactants, products, compositions)
    if coefficients is None:
        return None
    left = tuple((formula, coefficients[index]) for index, formula in enumerate(reactants))
    right = tuple(
        (formula, coefficients[index + len(reactants)]) for index, formula in enumerate(products)
    )
    return Reaction(rule_id, rule["name"], left, right, tuple(conditions), explain)


def _lowest_salt(kb: KnowledgeBase, metal: str, anion: str):
    for candidate in sorted(kb.elements[metal]["valence"]):
        product = _salt(kb, metal, anion, candidate)
        if product is not None:
            return candidate, product
    return None, None


def _metals(kb: KnowledgeBase):
    return [item for item in kb.compounds.values() if item.class_id == "don_chat_kim_loai"]


def _acids(kb: KnowledgeBase):
    return [item for item in kb.compounds.values() if item.class_id == "axit"]


def _bases(kb: KnowledgeBase):
    return [item for item in kb.compounds.values() if item.class_id == "bazo"]


def _salts(kb: KnowledgeBase):
    return [item for item in kb.compounds.values() if item.class_id in {"muoi_trung_hoa", "muoi_axit"}]


def _element_symbol(compound) -> str | None:
    others = [symbol for symbol in compound.comp if symbol != "O"]
    if len(others) == 1 and "O" in compound.comp:
        return others[0]
    if set(compound.comp) == {"H"}:
        return "H"
    return None


def _groups_of(kb: KnowledgeBase, symbol: str) -> set[str]:
    element = kb.elements.get(symbol)
    if element is None:
        return set()
    return set(element.get("groups") or [])


def _oxides_of(kb: KnowledgeBase, symbol: str):
    return [
        compound
        for compound in kb.compounds.values()
        if set(compound.comp) == {symbol, "O"}
    ]


def _acid_of_oxide(kb: KnowledgeBase, oxide):
    element = _element_symbol(oxide)
    if element is None:
        return None
    found = []
    for acid in _acids(kb):
        if set(acid.comp) - {"H", "O"} != {element}:
            continue
        acid_count = acid.comp[element]
        oxide_count = oxide.comp[element]
        if acid_count == 0 or oxide_count % acid_count != 0:
            continue
        multiplier = oxide_count // acid_count
        hydrogen = acid.comp.get("H", 0)
        if hydrogen == 0 or (multiplier * hydrogen) % 2 != 0:
            continue
        water = multiplier * hydrogen // 2
        if multiplier * acid.comp.get("O", 0) != oxide.comp.get("O", 0) + water:
            continue
        found.append(acid)
    if len(found) != 1:
        return None
    return found[0]


def _gas_by_anion(kb: KnowledgeBase) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for acid in _acids(kb):
        element = next((symbol for symbol in acid.comp if symbol not in {"H", "O"}), None)
        if element is None or acid.ions is None:
            continue
        for oxide in _oxides_of(kb, element):
            if oxide.class_id == "oxit_axit" and _acid_of_oxide(kb, oxide) == acid:
                mapping[acid.ions["anion"]["formula"]] = oxide.formula
    anions = {item["formula"]: item for item in kb.r1["anions"]}
    for formula in kb.r1["acid_salt_anions"]:
        anion = anions.get(formula)
        if anion is None:
            continue
        parent_map = {
            item["element"]: item["quantity"]
            for item in anion["composition"]
            if item["element"] != "H"
        }
        for candidate, gas in list(mapping.items()):
            candidate_anion = anions[candidate]
            candidate_map = {item["element"]: item["quantity"] for item in candidate_anion["composition"]}
            if candidate_map == parent_map:
                mapping[formula] = gas
    return mapping


def _amphoteric_anion(kb: KnowledgeBase, metal: str) -> str | None:
    for anion in kb.r1["anions"]:
        elements = {item["element"] for item in anion["composition"]}
        if elements == {metal, "O"} and "luong_tinh" in _groups_of(kb, metal):
            return anion["formula"]
    return None


def _alkali_bases(kb: KnowledgeBase, rule):
    allowed = set(rule["solubility"])
    for base in _bases(kb):
        if base.solubility not in allowed:
            continue
        if "kiem" not in _groups_of(kb, base.ions["cation"]):
            continue
        yield base


def _extra_conditions(rule, formula: str) -> list[str]:
    for item in rule["conditions_for"]:
        if item["formula"] == formula:
            return list(item["conditions"])
    return []


def _elemental_form(kb: KnowledgeBase, symbol: str) -> str | None:
    matches = [
        compound.formula
        for compound in kb.compounds.values()
        if compound.class_id in {"don_chat_kim_loai", "don_chat_phi_kim"} and set(compound.comp) == {symbol}
    ]
    if len(matches) != 1:
        return None
    return matches[0]


def _anion_definition(kb: KnowledgeBase, formula: str) -> dict:
    return next(item for item in kb.r1["anions"] if item["formula"] == formula)


def _acid_base(kb, rule):
    for acid in _acids(kb):
        for base in _bases(kb):
            salt = _salt(kb, base.ions["cation"], acid.ions["anion"]["formula"], base.valence)
            if salt is None:
                continue
            explain = f"{rule['name']}: cation {base.ions['cation']} kết hợp anion {acid.ions['anion']['formula']}."
            yield _build(kb, rule, rule["id"], [acid.formula, base.formula], [salt.formula, "H2O"], [], explain)


def _basic_oxide_acid(kb, rule):
    oxides = [item for item in kb.compounds.values() if item.class_id in rule["classes"]]
    for oxide in oxides:
        metal = next(symbol for symbol in oxide.comp if symbol != "O")
        if oxide.valence is None:
            continue
        for acid in _acids(kb):
            salt = _salt(kb, metal, acid.ions["anion"]["formula"], oxide.valence)
            if salt is None:
                continue
            explain = f"{rule['name']}. Hoá trị của {metal} trong {oxide.formula} là {oxide.valence}."
            yield _build(kb, rule, rule["id"], [oxide.formula, acid.formula], [salt.formula, "H2O"], [], explain)


def _acidic_oxide_base(kb, rule):
    excluded = set(rule["exclude_compounds"])
    blocked = set(rule["exclude_solubility"])
    for oxide in kb.compounds.values():
        if oxide.class_id not in rule["classes"] or oxide.formula in excluded:
            continue
        acid = _acid_of_oxide(kb, oxide)
        if acid is None:
            continue
        anion = acid.ions["anion"]["formula"]
        for base in _bases(kb):
            if base.solubility in blocked:
                continue
            salt = _salt(kb, base.ions["cation"], anion, base.valence)
            if salt is None:
                continue
            explain = f"{rule['name']}. {oxide.formula} ứng với {acid.formula}, anion {anion}."
            yield _build(
                kb, rule, rule["id"], [oxide.formula, base.formula], [salt.formula, "H2O"], [], explain
            )


def _acidic_oxide_water(kb, rule):
    excluded = set(rule["exclude_compounds"])
    for oxide in kb.compounds.values():
        if oxide.class_id not in rule["classes"] or oxide.formula in excluded:
            continue
        acid = _acid_of_oxide(kb, oxide)
        if acid is None:
            continue
        explain = f"{rule['name']}. {oxide.formula} ứng với {acid.formula}."
        yield _build(kb, rule, rule["id"], [oxide.formula, "H2O"], [acid.formula], [], explain)


def _basic_oxide_water(kb, rule):
    groups = set(rule["groups"])
    for oxide in kb.compounds.values():
        if oxide.class_id not in rule["classes"] or oxide.valence is None:
            continue
        metal = _element_symbol(oxide)
        if metal is None or not groups & _groups_of(kb, metal):
            continue
        base = _hydroxide(kb, metal, oxide.valence)
        if base is None:
            continue
        explain = f"{rule['name']}. {metal} thuộc kim loại kiềm hoặc kiềm thổ."
        yield _build(kb, rule, rule["id"], [oxide.formula, "H2O"], [base.formula], [], explain)


def _metal_acid(kb, rule):
    hydrogen = kb.elements["H"]["activity"]
    for metal in _metals(kb):
        activity = kb.elements[metal.formula]["activity"]
        if activity is None or activity >= hydrogen:
            continue
        for acid in _acids(kb):
            if acid.formula in set(rule["exclude_acids"]):
                continue
            valence, salt = _lowest_salt(kb, metal.formula, acid.ions["anion"]["formula"])
            if salt is None:
                continue
            explain = (
                f"{rule['name']}. {metal.name} đứng trước hiđro "
                f"(mức hoạt động {activity} nhỏ hơn {hydrogen}), hoá trị {valence}."
            )
            yield _build(
                kb,
                rule,
                rule["id"],
                [metal.formula, acid.formula],
                [salt.formula, "H2"],
                _extra_conditions(rule, acid.formula),
                explain,
            )


def _metal_salt(kb, rule):
    excluded = set(rule["exclude_metals"])
    for metal in _metals(kb):
        if metal.formula in excluded:
            continue
        activity = kb.elements[metal.formula]["activity"]
        if activity is None:
            continue
        for salt in _salts(kb):
            cation = salt.ions["cation"]
            if cation in {"H", "NH4"} or cation not in kb.elements:
                continue
            other = kb.elements[cation]["activity"]
            if other is None or not activity < other:
                continue
            if salt.solubility not in rule["solubility"]:
                continue
            valence, product = _lowest_salt(kb, metal.formula, salt.ions["anion"]["formula"])
            if product is None or product.formula == salt.formula:
                continue
            if cation not in kb.compounds:
                continue
            explain = (
                f"{rule['name']}. {metal.formula} hoạt động hơn {cation} "
                f"({activity} < {other}). Muối mới lấy hoá trị thấp {valence}."
            )
            yield _build(
                kb,
                rule,
                rule["id"],
                [metal.formula, salt.formula],
                [product.formula, cation],
                [],
                explain,
            )


def _metal_water(kb, rule):
    groups = set(rule["groups"])
    for metal in _metals(kb):
        if not groups & _groups_of(kb, metal.formula):
            continue
        valence = sorted(kb.elements[metal.formula]["valence"])[0]
        base = _hydroxide(kb, metal.formula, valence)
        if base is None:
            continue
        explain = f"{rule['name']}."
        yield _build(
            kb,
            rule,
            rule["id"],
            [metal.formula, "H2O"],
            [base.formula, "H2"],
            _extra_conditions(rule, metal.formula),
            explain,
        )


def _amphoteric_subjects(kb: KnowledgeBase, rule):
    groups = set(rule["groups"])
    for compound in kb.compounds.values():
        if compound.class_id not in rule["classes"]:
            continue
        if compound.class_id == "oxit_luong_tinh":
            metal, kind = _element_symbol(compound), "oxit"
        elif compound.class_id == "bazo" and compound.ions:
            metal, kind = compound.ions["cation"], "hidroxit"
        elif compound.class_id == "don_chat_kim_loai":
            metal, kind = compound.formula, "kim_loai"
        else:
            continue
        if metal and groups & _groups_of(kb, metal):
            yield compound.formula, metal, kind


def _amphoteric(kb, rule):
    for formula, metal, kind in _amphoteric_subjects(kb, rule):
        anion = _amphoteric_anion(kb, metal)
        if anion is None:
            continue
        for base in _alkali_bases(kb, rule):
            salt = _salt(kb, base.ions["cation"], anion, base.valence)
            if salt is None:
                continue
            explain = f"{rule['name']}. {metal} tạo anion {anion}."
            if kind == "kim_loai":
                built = _build(
                    kb, rule, rule["id"], [formula, base.formula], [salt.formula, "H2"], [], explain
                )
                if built is None:
                    built = _build(
                        kb,
                        rule,
                        rule["id"],
                        [formula, base.formula, "H2O"],
                        [salt.formula, "H2"],
                        [],
                        explain,
                    )
                yield built
            else:
                yield _build(
                    kb, rule, rule["id"], [formula, base.formula], [salt.formula, "H2O"], [], explain
                )


def _salt_acid_gas(kb, rule):
    gases = _gas_by_anion(kb)
    blocked_anions = set(rule["exclude_anions"])
    blocked_acids = set(rule["exclude_acids"])
    for salt in _salts(kb):
        anion = salt.ions["anion"]["formula"]
        gas = gases.get(anion)
        if gas is None or anion in blocked_anions:
            continue
        for acid in _acids(kb):
            if acid.formula in blocked_acids or acid.ions["anion"]["formula"] == anion:
                continue
            product = _salt(kb, salt.ions["cation"], acid.ions["anion"]["formula"], salt.valence)
            if product is None:
                continue
            explain = f"{rule['name']}. Anion {anion} ứng với khí {gas}."
            yield _build(
                kb,
                rule,
                rule["id"],
                [salt.formula, acid.formula],
                [product.formula, gas, "H2O"],
                [],
                explain,
            )


def _exchange_ok(compound) -> bool:
    return compound.solubility in {"khong_tan", "it_tan"}


def _salt_base(kb, rule):
    for salt in _salts(kb):
        if salt.solubility != "tan":
            continue
        for base in _bases(kb):
            if base.solubility not in rule["solubility"]:
                continue
            new_salt = _salt(kb, base.ions["cation"], salt.ions["anion"]["formula"], base.valence)
            new_base = _hydroxide(kb, salt.ions["cation"], salt.valence)
            if new_salt is None or new_base is None:
                continue
            if {new_salt.formula, new_base.formula} == {salt.formula, base.formula}:
                continue
            marks = []
            for product in (new_salt, new_base):
                if _exchange_ok(product):
                    result, rule_id = solubility_rule(product.ions["cation"], product.ions["anion"]["formula"], kb.r1)
                    marks.append(f"{product.formula} {result} theo {rule_id}")
            if not marks:
                continue
            explain = f"{rule['name']}. " + "; ".join(marks) + "."
            yield _build(
                kb,
                rule,
                rule["id"],
                [salt.formula, base.formula],
                [new_salt.formula, new_base.formula],
                [],
                explain,
            )


def _salt_salt(kb, rule):
    salts = [item for item in _salts(kb) if item.solubility in rule["solubility"]]
    for index, first in enumerate(salts):
        for second in salts[index + 1 :]:
            if first.ions["cation"] == second.ions["cation"] or first.ions["anion"]["formula"] == second.ions["anion"]["formula"]:
                continue
            product_a = _salt(kb, first.ions["cation"], second.ions["anion"]["formula"], first.valence)
            product_b = _salt(kb, second.ions["cation"], first.ions["anion"]["formula"], second.valence)
            if product_a is None or product_b is None:
                continue
            if {product_a.formula, product_b.formula} == {first.formula, second.formula}:
                continue
            marks = []
            for product in (product_a, product_b):
                if _exchange_ok(product):
                    result, rule_id = solubility_rule(product.ions["cation"], product.ions["anion"]["formula"], kb.r1)
                    marks.append(f"{product.formula} {result} theo {rule_id}")
            if not marks:
                continue
            explain = f"{rule['name']}. " + "; ".join(marks) + "."
            yield _build(
                kb,
                rule,
                rule["id"],
                [first.formula, second.formula],
                [product_a.formula, product_b.formula],
                [],
                explain,
            )


def _hydroxide_heat(kb, rule):
    for base in _bases(kb):
        if base.solubility not in rule["solubility"]:
            continue
        oxide = _oxide_of(kb, base.ions["cation"], base.valence)
        if oxide is None:
            continue
        result, rule_id = solubility_rule(base.ions["cation"], "OH", kb.r1)
        explain = f"{rule['name']}. {base.formula} có độ tan {result} theo {rule_id}."
        yield _build(kb, rule, rule["id"], [base.formula], [oxide, "H2O"], rule["conditions"], explain)


def _carbonate_heat(kb, rule):
    excluded = set(rule["exclude_cations"])
    for salt in _salts(kb):
        if salt.ions["anion"]["formula"] != "CO3" or salt.ions["cation"] in excluded:
            continue
        oxide = _oxide_of(kb, salt.ions["cation"], salt.valence)
        if oxide is None:
            continue
        explain = f"{rule['name']}. {salt.ions['cation']} không thuộc nhóm natri, kali, amoni."
        yield _build(kb, rule, rule["id"], [salt.formula], [oxide, "CO2"], rule["conditions"], explain)


def _ammonia_acid(kb, rule):
    for acid in _acids(kb):
        salt = _salt(kb, "NH4", acid.ions["anion"]["formula"], 1)
        if salt is None:
            continue
        explain = f"{rule['name']}."
        yield _build(kb, rule, rule["id"], ["NH3", acid.formula], [salt.formula], [], explain)


def _burn_product(kb: KnowledgeBase, symbol: str, metal: bool) -> str | None:
    oxides = _oxides_of(kb, symbol)
    if metal:
        mixed = [item for item in oxides if item.class_id == "oxit_hon_hop"]
        if mixed:
            return mixed[0].formula
        ranked = [item for item in oxides if item.valence is not None]
        if not ranked:
            return None
        return max(ranked, key=lambda item: item.valence).formula
    acidic = [item for item in oxides if item.class_id == "oxit_axit"]
    if acidic:
        return min(acidic, key=lambda item: item.valence).formula
    neutral = [item for item in oxides if item.class_id == "oxit_trung_tinh"]
    if len(neutral) == 1:
        return neutral[0].formula
    return None


def _combustion(kb, rule):
    excluded = set(rule["exclude_compounds"])
    for element in kb.compounds.values():
        if element.class_id not in rule["classes"] or element.formula in excluded:
            continue
        symbol = next(iter(element.comp))
        product = _burn_product(kb, symbol, element.class_id == "don_chat_kim_loai")
        if product is None:
            continue
        explain = f"{rule['name']}. Sản phẩm là oxit của {symbol}."
        yield _build(
            kb, rule, rule["id"], [element.formula, rule["reagent"]], [product], rule["conditions"], explain
        )


def _metal_conc_sulfuric(kb, rule):
    hydrogen = kb.elements["H"]["activity"]
    excluded = set(rule["exclude_metals"])
    acid = kb.compounds[rule["reagent"]]
    for metal in _metals(kb):
        if metal.formula in excluded:
            continue
        activity = kb.elements[metal.formula]["activity"]
        if activity is None or activity <= hydrogen:
            continue
        valence, salt = _lowest_salt(kb, metal.formula, acid.ions["anion"]["formula"])
        if salt is None:
            continue
        explain = (
            f"{rule['name']}. {metal.formula} đứng sau hiđro "
            f"(mức hoạt động {activity} lớn hơn {hydrogen}), hoá trị {valence}."
        )
        yield _build(
            kb,
            rule,
            rule["id"],
            [metal.formula, acid.formula],
            [salt.formula, rule["gas"], "H2O"],
            rule["conditions"],
            explain,
        )


def _hydrogen_reduction(kb, rule):
    excluded = set(rule["exclude_metals"])
    for oxide in kb.compounds.values():
        if oxide.class_id not in rule["classes"]:
            continue
        metal = _element_symbol(oxide)
        if metal is None or metal in excluded or metal not in kb.compounds:
            continue
        explain = f"{rule['name']}. Oxit của {metal} bị khử thành kim loại."
        yield _build(
            kb,
            rule,
            rule["id"],
            [oxide.formula, rule["reagent"]],
            [metal, "H2O"],
            rule["conditions"],
            explain,
        )


def _mixed_oxide_acid(kb, rule):
    excluded = set(rule["exclude_acids"])
    for oxide in kb.compounds.values():
        if oxide.class_id not in rule["classes"]:
            continue
        metal = _element_symbol(oxide)
        if metal is None:
            continue
        valences = sorted(kb.elements[metal]["valence"])
        if len(valences) < 2:
            continue
        low, high = valences[0], valences[-1]
        for acid in _acids(kb):
            if acid.formula in excluded:
                continue
            salt_low = _salt(kb, metal, acid.ions["anion"]["formula"], low)
            salt_high = _salt(kb, metal, acid.ions["anion"]["formula"], high)
            if salt_low is None or salt_high is None or salt_low.formula == salt_high.formula:
                continue
            explain = f"{rule['name']}. {metal} có hoá trị {low} và {high}."
            yield _build(
                kb,
                rule,
                rule["id"],
                [oxide.formula, acid.formula],
                [salt_low.formula, salt_high.formula, "H2O"],
                [],
                explain,
            )


def _amphoteric_salt_acid(kb, rule):
    for salt in _salts(kb):
        if salt.class_id not in rule["classes"]:
            continue
        anion = salt.ions["anion"]["formula"]
        definition = _anion_definition(kb, anion)
        elements = {item["element"] for item in definition["composition"]}
        metals = elements - {"O"}
        if elements != metals | {"O"} or len(metals) != 1:
            continue
        metal = next(iter(metals))
        if not set(rule["groups"]) & _groups_of(kb, metal):
            continue
        valence = sorted(kb.elements[metal]["valence"])[-1]
        hydroxide = _hydroxide(kb, metal, valence)
        if hydroxide is None:
            continue
        for acid in _acids(kb):
            product = _salt(kb, salt.ions["cation"], acid.ions["anion"]["formula"], salt.valence)
            if product is None:
                continue
            explain = f"{rule['name']}. Anion {anion} về hidroxit {hydroxide.formula}."
            built = _build(
                kb,
                rule,
                rule["id"],
                [salt.formula, acid.formula],
                [hydroxide.formula, product.formula],
                [],
                explain,
            )
            if built is None:
                built = _build(
                    kb,
                    rule,
                    rule["id"],
                    [salt.formula, acid.formula, "H2O"],
                    [hydroxide.formula, product.formula],
                    [],
                    explain,
                )
            yield built


def _acidic_oxide_oxidation(kb, rule):
    excluded = set(rule["exclude_compounds"])
    for oxide in kb.compounds.values():
        if oxide.class_id not in rule["classes"] or oxide.formula in excluded or oxide.valence is None:
            continue
        element = _element_symbol(oxide)
        if element is None:
            continue
        higher = [
            item
            for item in _oxides_of(kb, element)
            if item.class_id in rule["classes"] and item.valence is not None and item.valence > oxide.valence
        ]
        if not higher:
            continue
        product = max(higher, key=lambda item: item.valence)
        explain = f"{rule['name']}. {oxide.formula} lên hoá trị {product.valence}, ra {product.formula}."
        yield _build(
            kb,
            rule,
            rule["id"],
            [oxide.formula, rule["reagent"]],
            [product.formula],
            rule["conditions"],
            explain,
        )


def _molten_electrolysis(kb, rule):
    groups = set(rule["groups"])
    excluded = set(rule["exclude_compounds"])
    for salt in _salts(kb):
        if salt.class_id not in rule["classes"] or salt.formula in excluded:
            continue
        cation = salt.ions["cation"]
        if not groups & _groups_of(kb, cation):
            continue
        anion = salt.ions["anion"]["formula"]
        definition = _anion_definition(kb, anion)
        symbols = [item["element"] for item in definition["composition"]]
        if "O" in symbols or len(symbols) != 1:
            continue
        metal = _elemental_form(kb, cation)
        nonmetal = _elemental_form(kb, symbols[0])
        if metal is None or nonmetal is None:
            continue
        explain = f"{rule['name']}. Anion {anion} không chứa oxi."
        yield _build(
            kb, rule, rule["id"], [salt.formula], [metal, nonmetal], rule["conditions"], explain
        )


GENERATORS = {
    "acid_base": _acid_base,
    "basic_oxide_acid": _basic_oxide_acid,
    "acidic_oxide_base": _acidic_oxide_base,
    "acidic_oxide_water": _acidic_oxide_water,
    "basic_oxide_water": _basic_oxide_water,
    "metal_acid": _metal_acid,
    "metal_salt": _metal_salt,
    "metal_water": _metal_water,
    "amphoteric_with_base": _amphoteric,
    "salt_acid_gas": _salt_acid_gas,
    "salt_base": _salt_base,
    "salt_salt": _salt_salt,
    "hydroxide_heat": _hydroxide_heat,
    "carbonate_heat": _carbonate_heat,
    "ammonia_acid": _ammonia_acid,
    "combustion": _combustion,
    "metal_conc_sulfuric": _metal_conc_sulfuric,
    "hydrogen_reduction": _hydrogen_reduction,
    "mixed_oxide_acid": _mixed_oxide_acid,
    "amphoteric_salt_acid": _amphoteric_salt_acid,
    "acidic_oxide_oxidation": _acidic_oxide_oxidation,
    "molten_electrolysis": _molten_electrolysis,
}


def ground_reactions(kb: KnowledgeBase) -> list[Reaction]:
    reactions: list[Reaction] = []
    seen = set()
    for rule in kb.r2["rules"]:
        for reaction in GENERATORS[rule["kind"]](kb, rule):
            if reaction is None:
                continue
            signature = (reaction.reactants, reaction.products, reaction.conditions)
            if signature in seen:
                continue
            seen.add(signature)
            reactions.append(reaction)
    return reactions


def ensure_reactions(kb: KnowledgeBase) -> list[Reaction]:
    if getattr(kb, "reactions", None) is None:
        kb.reactions = ground_reactions(kb)
    return kb.reactions
