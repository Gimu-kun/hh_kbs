"""Suy diễn tiến: luật sinh sản phẩm, không tra danh sách phản ứng cụ thể."""

from __future__ import annotations

from collections import defaultdict
from itertools import permutations

from app.core.balancer import BalanceError, balance_formulas
from app.core.constants import REACTION_TYPE_LABELS
from app.core.rules_match import class_matches
from app.core.species import AMPHOTERIC_METALS, ANION_COMPOSITION, ANIONS, Catalog, Species

# Khí làm sản phẩm trao đổi. Hiđro halogenua chỉ tính là khí ở luật riêng với H2SO4 đặc,
# vì trong dung dịch loãng HCl không bị đẩy ra khỏi muối clorua.
_EXCHANGE_GASES = {
    "H2", "O2", "N2", "CO2", "SO2", "H2S", "NH3", "NO", "NO2", "N2O", "CO", "PH3",
}
# Muối axit gặp bazơ thì bị trung hòa proton, không trao đổi thành hiđroxit.
_ACID_SALT_ANIONS = {"HCO3", "HSO4", "HSO3", "HS", "H2PO4", "HPO4"}


def _kind_class(species: Species) -> str:
    if species.kind == "metal":
        return "don_chat_kim_loai"
    if species.kind == "nonmetal":
        return "don_chat_phi_kim"
    if species.kind == "noble":
        return "don_chat_khi_hiem"
    if species.kind == "acid":
        return "axit"
    if species.kind == "base":
        return "bazo_tan" if species.solubility in {"tan", "it_tan"} else "bazo_khong_tan"
    if species.kind == "salt":
        composition = ANION_COMPOSITION.get(species.anion.formula if species.anion else "", {})
        if composition.get("H") and species.cation and species.cation.formula not in {"H", "NH4"}:
            return "muoi_axit"
        return "muoi_trung_hoa"
    if species.kind == "oxide":
        return {
            "basic": "oxit_bazo",
            "acidic": "oxit_axit",
            "amphoteric": "oxit_luong_tinh",
            "neutral": "oxit_trung_tinh",
            "mixed": "oxit_bazo",
            "peroxide": "oxit_bazo",
        }.get(species.oxide_kind or "", "oxit")
    if species.kind == "water":
        return "oxit_trung_tinh"
    return species.compound.get("class") or "hop_chat_khac"


def _element_of(species: Species) -> str | None:
    if species.kind in {"metal", "nonmetal", "noble"}:
        return species.element
    if species.cation and species.cation.formula not in {"H", "NH4"}:
        return species.cation.formula
    return species.element


def slot_ok(species: Species, slot: dict, catalog: Catalog) -> bool:
    if slot.get("formula_any") and species.formula not in slot["formula_any"]:
        return False
    if slot.get("formula_not") and species.formula in slot["formula_not"]:
        return False
    if slot.get("kind_any") and species.kind not in slot["kind_any"]:
        return False
    if slot.get("class_any"):
        declared = species.compound.get("class") or ""
        ontology = set(species.compound.get("ontology") or [])
        inferred = _kind_class(species)
        matched = False
        for name in slot["class_any"]:
            if class_matches(declared, name) or name in ontology or class_matches(inferred, name):
                matched = True
                break
        if not matched:
            return False
    if slot.get("oxide_kind") and species.oxide_kind not in slot["oxide_kind"]:
        return False
    if slot.get("anion_any") and (species.anion is None or species.anion.formula not in slot["anion_any"]):
        return False
    if slot.get("anion_not") and species.anion and species.anion.formula in slot["anion_not"]:
        return False
    if slot.get("soluble_any") and species.solubility not in slot["soluble_any"]:
        return False
    element = _element_of(species)
    if slot.get("groups_any"):
        groups = set((catalog.elements.get(element or "") or {}).get("groups") or [])
        if not groups.intersection(slot["groups_any"]):
            return False
    if slot.get("activity_before") and not _activity_before(catalog, element, slot["activity_before"]):
        return False
    if slot.get("activity_after") and not _activity_after(catalog, element, slot["activity_after"]):
        return False
    if slot.get("activity_from") and not _activity_at_least(catalog, element, slot["activity_from"]):
        return False
    if slot.get("activity_to") and not _activity_at_most(catalog, element, slot["activity_to"]):
        return False
    if slot.get("amphoteric") and element not in AMPHOTERIC_METALS:
        return False
    return True


def _activity_before(catalog: Catalog, element: str | None, reference: str) -> bool:
    """Mạnh hơn mốc: số hoạt động nhỏ hơn (H5, số nhỏ là mạnh hơn)."""
    activity = catalog.activity_of(element)
    limit = catalog.activity_of(reference)
    return activity is not None and limit is not None and activity < limit


def _activity_after(catalog: Catalog, element: str | None, reference: str) -> bool:
    activity = catalog.activity_of(element)
    limit = catalog.activity_of(reference)
    return activity is not None and limit is not None and activity > limit


def _activity_at_least(catalog: Catalog, element: str | None, reference: str) -> bool:
    """Yếu hơn hoặc bằng mốc (số hoạt động lớn hơn hoặc bằng)."""
    activity = catalog.activity_of(element)
    limit = catalog.activity_of(reference)
    return activity is not None and limit is not None and activity >= limit


def _activity_at_most(catalog: Catalog, element: str | None, reference: str) -> bool:
    activity = catalog.activity_of(element)
    limit = catalog.activity_of(reference)
    return activity is not None and limit is not None and activity <= limit


def _valence_choice(catalog: Catalog, element: str, choice: str) -> int | None:
    valences = [int(value) for value in (catalog.elements.get(element) or {}).get("valence") or [] if int(value) > 0]
    if not valences:
        return None
    return min(valences) if choice == "low" else max(valences)


def _collapse(formulas: list[str]) -> list[str]:
    result = []
    for formula in formulas:
        if formula and formula not in result:
            result.append(formula)
    return result


def _as_products(value) -> list[str] | None:
    if not value:
        return None
    return _collapse(list(value))


def _ion_product(catalog: Catalog, cation: str, charge: int, anion: str) -> list[str] | None:
    if cation == "NH4" and anion == "OH":
        return ["NH3", "H2O"]
    if cation == "H" and anion == "OH":
        return ["H2O"]
    # AgOH không bền, tách ngay thành Ag2O (SGK).
    if cation == "Ag" and anion == "OH":
        return ["Ag2O", "H2O"]
    if cation == "H" and anion in {"CO3", "HCO3"}:
        return ["CO2", "H2O"]
    if cation == "H" and anion in {"SO3", "HSO3"}:
        return ["SO2", "H2O"]
    if cation == "H" and anion in {"S", "HS"}:
        return ["H2S"]
    formula = catalog.salt(cation, charge, anion)
    if formula == "H2CO3":
        return ["CO2", "H2O"]
    if formula == "H2SO3":
        return ["SO2", "H2O"]
    if formula:
        return [formula]
    return None


def _pick(species: list[Species], kind: str) -> Species | None:
    for item in species:
        if item.kind == kind:
            return item
    return None


def _anhydride_acids(oxide: Species, catalog: Catalog) -> list[Species]:
    found = []
    for candidate in catalog.species.values():
        if candidate.kind != "acid":
            continue
        if _is_anhydride(oxide.composition, candidate.composition):
            found.append(candidate)
    return found


def _is_anhydride(oxide: dict[str, int], acid: dict[str, int]) -> bool:
    elements = set(oxide) | set(acid) | {"H", "O"}
    for copies_oxide in range(1, 4):
        for copies_acid in range(1, 5):
            difference: dict[str, int] = {}
            possible = True
            for element in elements:
                value = copies_acid * acid.get(element, 0) - copies_oxide * oxide.get(element, 0)
                if value < 0:
                    possible = False
                    break
                if value:
                    difference[element] = value
            if not possible or not difference:
                continue
            hydrogen = difference.get("H", 0)
            oxygen = difference.get("O", 0)
            if set(difference) <= {"H", "O"} and hydrogen > 0 and hydrogen == 2 * oxygen:
                return True
    return False


def _exchange_allowed(left: Species, right: Species) -> bool:
    kinds = {left.kind, right.kind}
    if kinds == {"salt"}:
        return left.solubility == "tan" and right.solubility == "tan"
    if kinds == {"salt", "base"}:
        salt = left if left.kind == "salt" else right
        base = right if left.kind == "salt" else left
        return salt.solubility == "tan" and base.solubility in {"tan", "it_tan"}
    if "acid" in kinds and "salt" in kinds:
        return True
    if "acid" in kinds and "base" in kinds:
        return True
    return False


def _exchange_occurs(reactants: list[str], products: list[str], catalog: Catalog) -> bool:
    if any(catalog.is_precipitate(formula) for formula in products):
        return True
    if any(formula in _EXCHANGE_GASES or catalog.is_gas(formula) and formula in _EXCHANGE_GASES for formula in products):
        return True
    reactant_kinds = {catalog.get(formula).kind for formula in reactants if catalog.get(formula)}
    if "H2O" in products and reactant_kinds == {"acid", "base"}:
        return True
    acids_in = [formula for formula in reactants if catalog.get(formula) and catalog.get(formula).kind == "acid"]
    acids_out = [formula for formula in products if catalog.get(formula) and catalog.get(formula).kind == "acid"]
    if acids_in and acids_out and catalog.acid_rank(acids_out[0]) < catalog.acid_rank(acids_in[0]):
        return True
    return False


def build_exchange(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    if len(species) != 2 or not _exchange_allowed(species[0], species[1]):
        return []
    left, right = species
    if not (left.cation and left.anion and right.cation and right.anion):
        return []
    if left.kind == "base" and right.anion.formula in _ACID_SALT_ANIONS:
        return []
    if right.kind == "base" and left.anion.formula in _ACID_SALT_ANIONS:
        return []
    first = _ion_product(catalog, left.cation.formula, left.cation.charge, right.anion.formula)
    second = _ion_product(catalog, right.cation.formula, right.cation.charge, left.anion.formula)
    if first is None or second is None:
        return []
    products = _collapse(first + second)
    reactants = [left.formula, right.formula]
    if sorted(products) == sorted(reactants):
        return []
    if not _exchange_occurs(reactants, products, catalog):
        return []
    return [products]


def build_neutralization(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    acid = _pick(species, "acid")
    base = _pick(species, "base")
    if acid is None or base is None or acid.anion is None or base.cation is None:
        return []
    results = []
    full = _ion_product(catalog, base.cation.formula, base.cation.charge, acid.anion.formula)
    if full:
        products = _collapse(full + ["H2O"])
        if "H2O" in products or full == ["H2O"]:
            results.append(_collapse(full if full == ["H2O"] else full + ["H2O"]))
    bare = {element: count for element, count in ANION_COMPOSITION.get(acid.anion.formula, {}).items() if element != "H"}
    for anion_name, composition, _charge in ANIONS:
        if anion_name == acid.anion.formula or "H" not in composition:
            continue
        without_hydrogen = {element: count for element, count in composition.items() if element != "H"}
        if without_hydrogen != bare:
            continue
        salt = catalog.salt(base.cation.formula, base.cation.charge, anion_name)
        if salt:
            results.append([salt, "H2O"])
    return results


def build_acid_salt(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    """Axit proton hóa dần muối của gốc đa bazơ (tạo muối axit)."""
    acid = _pick(species, "acid")
    salt = _pick(species, "salt")
    if acid is None or salt is None or salt.anion is None or salt.cation is None or acid.anion is None:
        return []
    ladder = {
        "CO3": ["HCO3"],
        "SO3": ["HSO3"],
        "SO4": ["HSO4"],
        "S": ["HS"],
        "PO4": ["HPO4", "H2PO4"],
        "HPO4": ["H2PO4"],
    }
    results = []
    for anion in ladder.get(salt.anion.formula, []):
        acid_salt = catalog.salt(salt.cation.formula, salt.cation.charge, anion)
        partner = _ion_product(catalog, salt.cation.formula, salt.cation.charge, acid.anion.formula)
        if acid_salt and partner:
            results.append(_collapse([acid_salt, *partner]))
    return results


def build_deprotonate(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    base = _pick(species, "base")
    salt = _pick(species, "salt")
    if base is None or salt is None or salt.anion is None or salt.cation is None or base.cation is None:
        return []
    step = {"HCO3": "CO3", "HSO4": "SO4", "HSO3": "SO3", "HS": "S", "H2PO4": "HPO4", "HPO4": "PO4"}
    anion = step.get(salt.anion.formula)
    if not anion:
        return []
    own = catalog.salt(salt.cation.formula, salt.cation.charge, anion)
    other = catalog.salt(base.cation.formula, base.cation.charge, anion)
    results = []
    if salt.cation.formula == base.cation.formula and own:
        results.append([own, "H2O"])
    if other and own and salt.cation.formula != base.cation.formula:
        results.append(_collapse([other, own, "H2O"]))
        hydroxide = catalog.salt(salt.cation.formula, salt.cation.charge, "OH")
        if hydroxide:
            results.append(_collapse([other, hydroxide, "H2O"]))
    return results


def build_metal_acid_hydrogen(species: list[Species], catalog: Catalog, args: dict, _condition: str) -> list[list[str]]:
    metal = _pick(species, "metal")
    acid = _pick(species, "acid")
    if metal is None or acid is None or metal.element is None or acid.anion is None:
        return []
    valence = _valence_choice(catalog, metal.element, args.get("valence") or "low")
    if valence is None:
        return []
    salt = catalog.salt(metal.element, valence, acid.anion.formula)
    if not salt:
        return []
    return [[salt, "H2"]]


def build_metal_nitric(species: list[Species], catalog: Catalog, args: dict, _condition: str) -> list[list[str]]:
    metal = _pick(species, "metal")
    acid = _pick(species, "acid")
    if metal is None or acid is None or metal.element is None:
        return []
    valence = _valence_choice(catalog, metal.element, "high")
    salt = catalog.salt(metal.element, valence, "NO3") if valence else None
    if salt is None and valence:
        salt = catalog.salt(metal.element, _valence_choice(catalog, metal.element, "low") or valence, "NO3")
    if not salt:
        return []
    if args.get("reduced") == "NO2":
        modes = ["NO2"]
    elif _activity_before(catalog, metal.element, "H"):
        modes = ["NO", "N2O", "N2", "NH4NO3"]
    else:
        modes = ["NO"]
    results = []
    for mode in modes:
        if mode == "NH4NO3":
            results.append([salt, "NH4NO3", "H2O"])
        else:
            results.append([salt, mode, "H2O"])
    return results


def build_metal_conc_sulfuric(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    metal = _pick(species, "metal")
    if metal is None or metal.element is None:
        return []
    valence = _valence_choice(catalog, metal.element, "high")
    salt = catalog.salt(metal.element, valence, "SO4") if valence else None
    if not salt:
        return []
    modes = ["SO2", "S", "H2S"] if _activity_before(catalog, metal.element, "H") else ["SO2"]
    return [[salt, mode, "H2O"] for mode in modes]


def build_acid_oxide(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    acid = _pick(species, "acid")
    oxide = _pick(species, "oxide")
    if acid is None or oxide is None or acid.anion is None:
        return []
    if oxide.oxide_kind == "mixed" and oxide.element:
        salts = []
        for valence in oxide.mixed_valences:
            salt = catalog.salt(oxide.element, valence, acid.anion.formula)
            if salt and salt not in salts:
                salts.append(salt)
        return [salts + ["H2O"]] if salts else []
    if oxide.oxide_kind not in {"basic", "amphoteric"} or oxide.cation is None:
        return []
    salt = catalog.salt(oxide.cation.formula, oxide.cation.charge, acid.anion.formula)
    if not salt:
        return []
    return [[salt, "H2O"]]


def build_oxide_oxidized(species: list[Species], catalog: Catalog, _args: dict, condition: str) -> list[list[str]]:
    acid = _pick(species, "acid")
    oxide = _pick(species, "oxide")
    if acid is None or oxide is None or oxide.element is None or acid.anion is None:
        return []
    high = _valence_choice(catalog, oxide.element, "high")
    if high is None:
        return []
    if oxide.oxide_kind != "mixed" and oxide.metal_valence is not None and oxide.metal_valence >= high:
        return []
    salt = catalog.salt(oxide.element, high, acid.anion.formula)
    if not salt:
        return []
    if acid.formula == "HNO3":
        reduced = "NO" if condition == "DILUTE" else "NO2"
        return [[salt, reduced, "H2O"]]
    if acid.formula == "H2SO4":
        return [[salt, "SO2", "H2O"]]
    return []


def build_basic_oxide_water(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    oxide = _pick(species, "oxide")
    if oxide is None or oxide.cation is None or oxide.oxide_kind != "basic":
        return []
    element = oxide.element or ""
    groups = set((catalog.elements.get(element) or {}).get("groups") or [])
    if "kiem" not in groups and not ("kiem_tho" in groups and element not in {"Be", "Mg"}):
        return []
    hydroxide = catalog.salt(oxide.cation.formula, oxide.cation.charge, "OH")
    return [[hydroxide]] if hydroxide else []


def build_acidic_oxide_water(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    oxide = _pick(species, "oxide")
    if oxide is None or oxide.formula == "SiO2" or oxide.oxide_kind != "acidic":
        return []
    return [[acid.formula] for acid in _anhydride_acids(oxide, catalog)]


def build_oxide_oxide(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    basic = next((item for item in species if item.oxide_kind in {"basic", "amphoteric"} and item.cation), None)
    acidic = next((item for item in species if item.oxide_kind == "acidic"), None)
    if basic is None or acidic is None or basic.cation is None:
        return []
    results = []
    for acid in _anhydride_acids(acidic, catalog):
        if acid.anion is None:
            continue
        salt = catalog.salt(basic.cation.formula, basic.cation.charge, acid.anion.formula)
        if salt:
            results.append([salt])
    return results


def build_acidic_oxide_base(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    oxide = _pick(species, "oxide")
    base = _pick(species, "base")
    if oxide is None or base is None or base.cation is None or oxide.oxide_kind != "acidic":
        return []
    results = []
    for acid in _anhydride_acids(oxide, catalog):
        if acid.anion is None:
            continue
        full = catalog.salt(base.cation.formula, base.cation.charge, acid.anion.formula)
        if full:
            results.append([full, "H2O"])
        bare = {element: count for element, count in ANION_COMPOSITION.get(acid.anion.formula, {}).items() if element != "H"}
        for anion_name, composition, _charge in ANIONS:
            if "H" not in composition:
                continue
            without_hydrogen = {element: count for element, count in composition.items() if element != "H"}
            if without_hydrogen != bare:
                continue
            salt = catalog.salt(base.cation.formula, base.cation.charge, anion_name)
            if salt:
                results.append([salt])
                results.append([salt, "H2O"])
    return results


def build_binary(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    if len(species) != 2:
        return []
    left, right = species
    if left.kind not in {"metal", "nonmetal"} or right.kind not in {"metal", "nonmetal"}:
        return []
    if not left.element or not right.element or left.element == right.element:
        return []
    elements = {left.element, right.element}
    formulas = {left.formula, right.formula}
    if "O2" in formulas and elements.intersection({"Au", "Pt"}):
        return []
    results = []
    for candidate in catalog.species.values():
        if candidate.formula in formulas:
            continue
        if set(candidate.composition) <= elements and left.element in candidate.composition and right.element in candidate.composition:
            results.append([candidate.formula])
    return results


def build_hydroxide_heat(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    base = species[0]
    if base.kind != "base" or base.cation is None:
        return []
    oxide = catalog.oxide(base.cation.formula, base.cation.charge)
    return [[oxide, "H2O"]] if oxide else []


def build_carbonate_heat(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    salt = species[0]
    if salt.anion is None or salt.anion.formula != "CO3" or salt.cation is None:
        return []
    if salt.cation.formula == "NH4":
        return [["NH3", "CO2", "H2O"]]
    metal = salt.cation.formula
    groups = set((catalog.elements.get(metal) or {}).get("groups") or [])
    # Cacbonat kim loại kiềm (trừ Li) bền nhiệt trong chương trình phổ thông.
    if "kiem" in groups and metal != "Li":
        return []
    oxide = catalog.oxide(metal, salt.cation.charge)
    return [[oxide, "CO2"]] if oxide else []


def build_bicarbonate_heat(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    salt = species[0]
    if salt.anion is None or salt.anion.formula != "HCO3" or salt.cation is None:
        return []
    if salt.cation.formula == "NH4":
        return [["NH3", "CO2", "H2O"]]
    carbonate = catalog.salt(salt.cation.formula, salt.cation.charge, "CO3")
    return [[carbonate, "CO2", "H2O"]] if carbonate else []


def build_nitrate_heat(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    salt = species[0]
    if salt.anion is None or salt.anion.formula != "NO3" or salt.cation is None:
        return []
    cation = salt.cation.formula
    if cation == "NH4":
        return [["N2O", "H2O"]]
    charge = salt.cation.charge
    if cation == "Li" or _activity_at_least(catalog, cation, "Mg") and _activity_at_most(catalog, cation, "Cu"):
        oxide = catalog.oxide(cation, charge)
        return [[oxide, "NO2", "O2"]] if oxide else []
    if _activity_before(catalog, cation, "Mg"):
        nitrite = catalog.salt(cation, charge, "NO2")
        return [[nitrite, "O2"]] if nitrite else []
    if _activity_after(catalog, cation, "Cu"):
        if cation in catalog.compounds:
            return [[cation, "NO2", "O2"]]
    return []


def build_ammonium_heat(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    salt = species[0]
    if salt.cation is None or salt.cation.formula != "NH4" or salt.anion is None:
        return []
    anion = salt.anion.formula
    hydrogen = {"Cl": "HCl", "Br": "HBr", "I": "HI", "SO4": "H2SO4", "NO3": None}.get(anion, None)
    if anion == "NO3":
        return [["N2O", "H2O"]]
    if anion == "NO2":
        return [["N2", "H2O"]]
    if anion in {"CO3", "HCO3"}:
        return [["NH3", "CO2", "H2O"]]
    if hydrogen and hydrogen in catalog.compounds:
        return [["NH3", hydrogen]]
    return []


def build_electrolysis_melt(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    item = species[0]
    if item.formula == "Al2O3":
        return [["Al", "O2"]]
    if item.kind == "salt" and item.anion and item.anion.formula == "Cl" and item.cation:
        metal = item.cation.formula
        if metal in catalog.compounds:
            return [[metal, "Cl2"]]
    if item.kind == "base" and item.cation and item.cation.formula in {"Na", "K", "Li"}:
        return [[item.cation.formula, "O2", "H2O"]]
    return []


def build_electrolysis_solution(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    salt = species[0]
    if salt.kind != "salt" or salt.cation is None or salt.anion is None:
        return []
    if not _activity_after(catalog, salt.cation.formula, "H"):
        return []
    acid = catalog.salt("H", 1, salt.anion.formula)
    metal = salt.cation.formula
    if acid and metal in catalog.compounds:
        return [[metal, "O2", acid]]
    return []


_HALOGEN_ORDER = ["F2", "Cl2", "Br2", "I2"]
_HALIDE_OF = {"F2": "F", "Cl2": "Cl", "Br2": "Br", "I2": "I"}
_ELEMENT_OF_HALIDE = {"F": "F2", "Cl": "Cl2", "Br": "Br2", "I": "I2"}


def build_halogen_displace(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    halogen = next((item for item in species if item.formula in _HALOGEN_ORDER), None)
    salt = _pick(species, "salt")
    if halogen is None or salt is None or salt.anion is None or salt.cation is None:
        return []
    if salt.anion.formula not in _ELEMENT_OF_HALIDE or salt.solubility != "tan":
        return []
    freed = _ELEMENT_OF_HALIDE[salt.anion.formula]
    if _HALOGEN_ORDER.index(halogen.formula) >= _HALOGEN_ORDER.index(freed):
        return []
    product = catalog.salt(salt.cation.formula, salt.cation.charge, _HALIDE_OF[halogen.formula])
    return [[product, freed]] if product else []


def build_metal_displace(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    metal = _pick(species, "metal")
    salt = _pick(species, "salt")
    if metal is None or salt is None or metal.element is None or salt.cation is None or salt.anion is None:
        return []
    if salt.cation.formula in {"H", "NH4"} or salt.solubility != "tan":
        return []
    # Kim loại mạnh hơn Na phản ứng với nước, không đẩy được kim loại khỏi dung dịch muối.
    if not _activity_after(catalog, metal.element, "Na"):
        return []
    if not _activity_before(catalog, metal.element, salt.cation.formula):
        return []
    valence = _valence_choice(catalog, metal.element, "low")
    product = catalog.salt(metal.element, valence, salt.anion.formula) if valence else None
    if product and salt.cation.formula in catalog.compounds:
        return [[product, salt.cation.formula]]
    return []


def build_fe3_reduced(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    """Cu khử Fe3+ thành Fe2+ trong dung dịch — ngoại lệ SGK, không đẩy được Fe ra khỏi muối."""
    metal = _pick(species, "metal")
    salt = _pick(species, "salt")
    if metal is None or salt is None or salt.cation is None or salt.anion is None:
        return []
    if metal.formula != "Cu" or salt.cation.formula != "Fe" or salt.cation.charge != 3:
        return []
    reduced = catalog.salt("Fe", 2, salt.anion.formula)
    oxidized = catalog.salt("Cu", 2, salt.anion.formula)
    return [[oxidized, reduced]] if reduced and oxidized else []


def build_reduce_oxide(species: list[Species], catalog: Catalog, args: dict, _condition: str) -> list[list[str]]:
    oxide = _pick(species, "oxide")
    reductant = next((item for item in species if item.formula in {"H2", "CO", "C", "Al", "Mg"}), None)
    if oxide is None or reductant is None or oxide.element is None:
        return []
    metal = oxide.element
    if reductant.formula == "Mg":
        if metal == "Mg":
            return []
        if catalog.activity_of(metal) is not None and not _activity_after(catalog, metal, "Mg"):
            return []
        if "MgO" in catalog.compounds and metal in catalog.compounds:
            return [["MgO", metal]]
        return []
    if reductant.formula == "Al":
        if metal == "Al" or oxide.oxide_kind == "acidic":
            return []
        if catalog.activity_of(metal) is not None and not _activity_after(catalog, metal, "Al"):
            return []
        return [["Al2O3", metal]] if "Al2O3" in catalog.compounds and metal in catalog.compounds else []
    if oxide.oxide_kind == "acidic":
        return []
    threshold = args.get("weaker_than") or "Fe"
    if not _activity_at_least(catalog, metal, threshold):
        return []
    if metal not in catalog.compounds:
        return []
    if reductant.formula == "H2":
        return [[metal, "H2O"]]
    if reductant.formula == "CO":
        return [[metal, "CO2"]]
    return [[metal, "CO2"], [metal, "CO"]]


def _complexes(catalog: Catalog, metal: str, alkali: str, banned: set[str]) -> list[str]:
    found = []
    for candidate in catalog.species.values():
        elements = set(candidate.composition)
        if metal in elements and alkali in elements and elements <= {metal, alkali, "O", "H"} and candidate.formula not in banned:
            found.append(candidate.formula)
    return found


def _amphoteric_element(species: Species) -> str | None:
    element = species.element or (species.cation.formula if species.cation else None)
    return element if element in AMPHOTERIC_METALS else None


def build_amphoteric_alkali(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    amph = next((item for item in species if _amphoteric_element(item) and item.kind in {"oxide", "base"}), None)
    base = next((item for item in species if item.kind == "base" and item is not amph), None)
    if amph is None or base is None or base.cation is None:
        return []
    metal = _amphoteric_element(amph)
    results = []
    for formula in _complexes(catalog, metal or "", base.cation.formula, {base.formula, amph.formula}):
        results.append([formula, "H2O"])
        results.append([formula])
    return results


def build_amphoteric_salt(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    salt = _pick(species, "salt")
    base = _pick(species, "base")
    if salt is None or base is None or salt.cation is None or salt.anion is None or base.cation is None:
        return []
    if salt.cation.formula not in AMPHOTERIC_METALS or salt.solubility != "tan":
        return []
    partner = catalog.salt(base.cation.formula, base.cation.charge, salt.anion.formula)
    if not partner:
        return []
    results = []
    for formula in _complexes(catalog, salt.cation.formula, base.cation.formula, {salt.formula, base.formula}):
        results.append([formula, partner])
        results.append([formula, partner, "H2O"])
    return results


def build_amphoteric_metal(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    metal = _pick(species, "metal")
    base = _pick(species, "base")
    if metal is None or base is None or metal.element is None or base.cation is None:
        return []
    if metal.element not in AMPHOTERIC_METALS:
        return []
    banned = {item.formula for item in species}
    results = []
    for formula in _complexes(catalog, metal.element, base.cation.formula, banned):
        results.append([formula, "H2"])
        results.append([formula, "H2", "H2O"])
    return results


def build_nonmetal_oxidation(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    simple = next((item for item in species if item.kind == "nonmetal"), None)
    acid = _pick(species, "acid")
    if simple is None or acid is None or simple.element is None:
        return []
    best_oxidation = None
    chosen: list[Species] = []
    for candidate in catalog.species.values():
        if candidate.kind != "acid" or simple.element not in candidate.oxidation:
            continue
        oxidation = candidate.oxidation[simple.element]
        if best_oxidation is None or oxidation > best_oxidation:
            best_oxidation = oxidation
            chosen = [candidate]
        elif oxidation == best_oxidation:
            chosen.append(candidate)
    if not chosen:
        return []
    reduced = "NO2" if acid.formula == "HNO3" else "SO2"
    results = []
    for candidate in chosen:
        if acid.formula == "H2SO4" and candidate.formula == "H2SO4":
            results.append(["SO2", "H2O"])
            continue
        product = candidate.formula
        extras = [reduced, "H2O"]
        if product == "H2CO3":
            results.append(_collapse(["CO2", "H2O", *extras]))
        elif product == "H2SO3":
            results.append(_collapse(["SO2", "H2O", *extras]))
        else:
            results.append(_collapse([product, *extras]))
    return results


def build_halide_sulfuric(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    salt = _pick(species, "salt")
    if salt is None or salt.anion is None or salt.cation is None or salt.anion.formula not in {"Cl", "Br", "I"}:
        return []
    hydrogen = {"Cl": "HCl", "Br": "HBr", "I": "HI"}[salt.anion.formula]
    results = []
    for anion in ("HSO4", "SO4"):
        product = catalog.salt(salt.cation.formula, salt.cation.charge, anion)
        if product:
            results.append([product, hydrogen])
    return results


def build_halogen_alkali(species: list[Species], catalog: Catalog, _args: dict, condition: str) -> list[list[str]]:
    halogen = next((item for item in species if item.formula in {"Cl2", "Br2", "I2"}), None)
    base = _pick(species, "base")
    if halogen is None or base is None or base.cation is None:
        return []
    table = {
        "Cl2": ("Cl", "ClO", "ClO3"),
        "Br2": ("Br", "BrO", "BrO3"),
        "I2": ("I", "IO", "IO3"),
    }
    halide, hypo, halate = table[halogen.formula]
    cation, charge = base.cation.formula, base.cation.charge
    salt_halide = catalog.salt(cation, charge, halide)
    salt_hypo = catalog.salt(cation, charge, hypo)
    salt_halate = catalog.salt(cation, charge, halate)
    results = []
    # Lạnh cho hipohalogenit, nóng cho halogenat. Sinh cả hai để khớp các bản ghi dùng chung mã điều kiện.
    if salt_halide and salt_hypo:
        results.append([salt_halide, salt_hypo, "H2O"])
    if salt_halide and salt_halate:
        results.append([salt_halide, salt_halate, "H2O"])
    if halogen.formula == "Cl2" and cation == "Ca" and "CaOCl2" in catalog.compounds:
        results.append(["CaOCl2", "H2O"])
    return results


def build_no2_water(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    if formulas == {"NO2", "H2O"}:
        return [["HNO3", "HNO2"]]
    if formulas == {"NO2", "O2", "H2O"}:
        return [["HNO3"]]
    return []


def build_no2_base(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    base = _pick(species, "base")
    if base is None or base.cation is None or not any(item.formula == "NO2" for item in species):
        return []
    nitrate = catalog.salt(base.cation.formula, base.cation.charge, "NO3")
    nitrite = catalog.salt(base.cation.formula, base.cation.charge, "NO2")
    return [[nitrate, nitrite, "H2O"]] if nitrate and nitrite else []


def build_binary_fixed(species: list[Species], _catalog: Catalog, args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    if formulas == set(args.get("reactants") or []):
        return [list(item) for item in args.get("products") or []]
    return []


def build_chlorate_heat(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    salt = species[0]
    if salt.anion is None or salt.anion.formula != "ClO3" or salt.cation is None:
        return []
    chloride = catalog.salt(salt.cation.formula, salt.cation.charge, "Cl")
    perchlorate = catalog.salt(salt.cation.formula, salt.cation.charge, "ClO4")
    results = []
    if chloride:
        results.append([chloride, "O2"])
    if chloride and perchlorate:
        results.append([chloride, perchlorate])
    return results


def build_permanganate_heat(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    salt = species[0]
    if salt.formula == "KMnO4":
        return [["K2MnO4", "MnO2", "O2"]]
    return []


def build_nitride_water(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    compound = next((item for item in species if item.formula != "H2O"), None)
    if compound is None or set(compound.composition) < {"N"} or len(compound.composition) != 2:
        return []
    metal = next(element for element in compound.composition if element != "N")
    if not _element_is_metal(catalog, metal):
        return []
    nitrogen = compound.composition["N"]
    count = compound.composition[metal]
    if (3 * nitrogen) % count != 0:
        return []
    charge = (3 * nitrogen) // count
    hydroxide = catalog.salt(metal, charge, "OH")
    return [[hydroxide, "NH3"]] if hydroxide else []


def _element_is_metal(catalog: Catalog, symbol: str) -> bool:
    return (catalog.elements.get(symbol) or {}).get("type") == "kim_loai"


def build_sulfide_roast(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    salt = next((item for item in species if item.formula != "O2"), None)
    if salt is None:
        return []
    metal = None
    charge = None
    if salt.anion and salt.anion.formula == "S" and salt.cation:
        metal = salt.cation.formula
        charge = salt.cation.charge
    else:
        metal = _metal_of_binary(salt, "S")
        charge = _valence_choice(catalog, metal, "high") if metal else None
    if not metal:
        return []
    results = []
    candidates = []
    if charge:
        candidates.append(catalog.oxide(metal, charge))
    high = _valence_choice(catalog, metal, "high")
    if high:
        candidates.append(catalog.oxide(metal, high))
    for candidate in candidates:
        if candidate and [candidate, "SO2"] not in results:
            results.append([candidate, "SO2"])
    if metal in catalog.compounds:
        results.append([metal, "SO2"])
    return results


def build_metal_co2(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    metal = _pick(species, "metal")
    if metal is None or metal.element is None:
        return []
    if not (_activity_at_least(catalog, metal.element, "Mg") and _activity_at_most(catalog, metal.element, "Al")):
        return []
    valence = _valence_choice(catalog, metal.element, "high")
    oxide = catalog.oxide(metal.element, valence) if valence else None
    return [[oxide, "C"]] if oxide else []


def build_metal_water(species: list[Species], catalog: Catalog, _args: dict, condition: str) -> list[list[str]]:
    metal = _pick(species, "metal")
    if metal is None or metal.element is None:
        return []
    element = metal.element
    groups = set((catalog.elements.get(element) or {}).get("groups") or [])
    valence = _valence_choice(catalog, element, "low") or _valence_choice(catalog, element, "high")
    results = []
    if condition in {"NONE", "HEAT"} and (
        "kiem" in groups or ("kiem_tho" in groups and element not in {"Be", "Mg"})
    ):
        hydroxide = catalog.salt(element, valence, "OH") if valence else None
        if hydroxide:
            results.append([hydroxide, "H2"])
    if condition != "HEAT":
        return results
    if element == "Fe":
        results.append(["Fe3O4", "H2"])
        results.append(["Fe2O3", "H2"])
        oxide = catalog.oxide("Fe", 2)
        if oxide:
            results.append([oxide, "H2"])
        return results
    if element in {"Mg", "Al", "Zn"} or element in AMPHOTERIC_METALS:
        hydroxide = catalog.salt(element, valence, "OH") if valence else None
        oxide = catalog.oxide(element, valence) if valence else None
        if hydroxide:
            results.append([hydroxide, "H2"])
        if oxide:
            results.append([oxide, "H2"])
    return results


def build_so2_halogen_water(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    halogen = formulas.intersection({"Cl2", "Br2", "I2"})
    if formulas.issuperset({"SO2", "H2O"}) and len(halogen) == 1 and formulas <= {"SO2", "H2O", "Cl2", "Br2", "I2"}:
        hydrogen = {"Cl2": "HCl", "Br2": "HBr", "I2": "HI"}[next(iter(halogen))]
        return [["H2SO4", hydrogen]]
    return []


def build_ammonia_acid(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    acid = _pick(species, "acid")
    if acid is None or acid.anion is None or not any(item.formula == "NH3" for item in species):
        return []
    salt = catalog.salt("NH4", 1, acid.anion.formula)
    return [[salt]] if salt else []


def _metal_of_binary(species: Species, other: str) -> str | None:
    composition = species.composition
    if other not in composition or len(composition) != 2:
        return None
    return next(element for element in composition if element != other)


def build_reducing_salt(species: list[Species], catalog: Catalog, _args: dict, condition: str) -> list[list[str]]:
    """Muối hoặc sunfua hóa trị thấp bị HNO3 hoặc H2SO4 đặc oxi hóa."""
    acid = _pick(species, "acid")
    other = next((item for item in species if item is not acid), None)
    if acid is None or other is None or acid.formula not in {"HNO3", "H2SO4"}:
        return []
    metal = None
    anion = other.anion.formula if other.anion else None
    charge = other.cation.charge if other.cation else None
    if other.cation and other.cation.formula not in {"H", "NH4"}:
        metal = other.cation.formula
    else:
        metal = _metal_of_binary(other, "S")
        if metal:
            anion = "S"
    if metal is None:
        return []
    high = _valence_choice(catalog, metal, "high") or charge
    if high is None:
        return []
    if acid.formula == "HNO3":
        reduced = "NO" if condition == "DILUTE" else "NO2"
        salt_anion = "NO3"
    else:
        reduced = "SO2"
        salt_anion = "SO4"
    salt = catalog.salt(metal, high, salt_anion)
    if salt is None and charge:
        salt = catalog.salt(metal, charge, salt_anion)
    if not salt:
        return []
    results = []
    if anion in {"CO3", "HCO3"}:
        results.append([salt, reduced, "CO2", "H2O"])
    if anion == "S":
        results.append([salt, "H2SO4", reduced, "H2O"])
        results.append([salt, reduced, "H2O"])
        results.append([salt, "SO2", "S", "H2O"])
        sulfate = catalog.salt(metal, high, "SO4")
        if acid.formula == "HNO3" and sulfate:
            results.append([salt, sulfate, reduced, "H2O"])
    if other.cation and charge is not None and high > charge and anion not in {"CO3", "HCO3", "S"}:
        results.append([salt, reduced, "H2O"])
    return results


def build_halogen_water(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    if "H2O" not in formulas:
        return []
    if "Cl2" in formulas:
        return [["HCl", "HClO"]]
    if "Br2" in formulas:
        return [["HBr", "HBrO"]]
    if "I2" in formulas:
        return [["HI", "HIO"]]
    return []


def build_hydride_water(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    compound = next((item for item in species if item.formula != "H2O"), None)
    if compound is None:
        return []
    metal = _metal_of_binary(compound, "H")
    if metal is None or (catalog.elements.get(metal) or {}).get("type") != "kim_loai":
        return []
    hydrogen = compound.composition["H"]
    count = compound.composition[metal]
    if hydrogen % count != 0:
        return []
    hydroxide = catalog.salt(metal, hydrogen // count, "OH")
    return [[hydroxide, "H2"]] if hydroxide else []


def build_hx_oxygen(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    table = {"HCl": "Cl2", "HBr": "Br2", "HI": "I2"}
    for acid, halogen in table.items():
        if formulas == {acid, "O2"}:
            return [[halogen, "H2O"]]
    return []


def build_halide_hydrolysis(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    compound = next((item for item in species if item.formula != "H2O"), None)
    if compound is None:
        return []
    halogens = {"Cl", "Br", "I", "F"}
    composition = compound.composition
    if len(composition) != 2:
        return []
    halogen = next((element for element in composition if element in halogens), None)
    if halogen is None:
        return []
    element = next(item for item in composition if item != halogen)
    hydrogen = {"Cl": "HCl", "Br": "HBr", "I": "HI", "F": "HF"}[halogen]
    results = []
    for candidate in catalog.species.values():
        if candidate.kind == "acid" and element in candidate.composition:
            results.append([candidate.formula, hydrogen])
        if candidate.kind == "oxide" and set(candidate.composition) <= {element, "O"} and element in candidate.composition:
            results.append([candidate.formula, hydrogen])
    return results


def build_peroxide_reaction(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    peroxide = next((item for item in species if item.oxide_kind == "peroxide" and item.cation), None)
    other = next((item for item in species if item is not peroxide), None)
    if peroxide is None or other is None or peroxide.cation is None:
        return []
    cation, charge = peroxide.cation.formula, peroxide.cation.charge
    if other.formula == "H2O":
        hydroxide = catalog.salt(cation, charge, "OH")
        return [[hydroxide, "O2"]] if hydroxide else []
    if other.formula == "CO2":
        carbonate = catalog.salt(cation, charge, "CO3")
        return [[carbonate, "O2"]] if carbonate else []
    return []


def build_h2s_oxygen(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    if formulas == {"H2S", "O2"}:
        return [["SO2", "H2O"], ["S", "H2O"]]
    if formulas == {"H2S", "Cl2"}:
        return [["HCl", "S"]]
    if formulas == {"H2S", "Br2"}:
        return [["HBr", "S"]]
    if formulas == {"SO2", "H2S"}:
        return [["S", "H2O"]]
    return []


def build_carbon_gases(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    if formulas == {"C", "H2O"}:
        return [["CO", "H2"], ["CO2", "H2"]]
    if formulas == {"C", "CO2"}:
        return [["CO"]]
    return []


def build_lab_chlorine(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    if "HCl" not in formulas:
        return []
    if "MnO2" in formulas:
        return [["MnCl2", "Cl2", "H2O"]]
    if "KMnO4" in formulas:
        return [["KCl", "MnCl2", "Cl2", "H2O"]]
    if "K2Cr2O7" in formulas:
        return [["KCl", "CrCl3", "Cl2", "H2O"]]
    if "PbO2" in formulas:
        return [["PbCl2", "Cl2", "H2O"]]
    return []


def build_electrolysis_aqueous(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    salt = _pick(species, "salt")
    if salt is None or salt.cation is None or salt.anion is None:
        return []
    if not any(item.formula == "H2O" for item in species):
        return []
    cation, charge, anion = salt.cation.formula, salt.cation.charge, salt.anion.formula
    if _activity_after(catalog, cation, "H"):
        if anion in _ELEMENT_OF_HALIDE:
            return [[cation, _ELEMENT_OF_HALIDE[anion], "H2O"]]
        acid = catalog.salt("H", 1, anion)
        return [[cation, "O2", acid]] if acid else []
    if anion in _ELEMENT_OF_HALIDE:
        base = catalog.salt(cation, charge, "OH")
        if base:
            return [[base, "H2", _ELEMENT_OF_HALIDE[anion]]]
    return []


def build_fe_hydroxide_air(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    if "Fe(OH)2" in formulas and "O2" in formulas:
        return [["Fe(OH)3"]]
    return []


def build_permanganate(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    if not any(item.formula == "KMnO4" for item in species):
        return []
    formulas = {item.formula for item in species}
    if formulas == {"KMnO4", "H2SO4"}:
        return [["Mn2O7", "K2SO4", "H2O"]]
    oxidized: list[str] = []
    if "H2O2" in formulas:
        oxidized = ["O2"]
    elif "SO2" in formulas:
        oxidized = ["H2SO4"]
    elif "HNO2" in formulas:
        oxidized = ["HNO3"]
    else:
        iron = next((item for item in species if item.cation and item.cation.formula == "Fe" and item.cation.charge == 2), None)
        if iron and iron.anion:
            high = catalog.salt("Fe", 3, iron.anion.formula)
            if high:
                oxidized = [high]
    if not oxidized:
        return []
    return [oxidized + ["K2SO4", "MnSO4", "H2O"]]


def build_unstable_acid(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formula = species[0].formula
    if formula == "H2CO3":
        return [["CO2", "H2O"]]
    if formula == "H2SO3":
        return [["SO2", "H2O"]]
    return []


def build_fixed(species: list[Species], _catalog: Catalog, args: dict, _condition: str) -> list[list[str]]:
    expected = args.get("reactants") or []
    if sorted(item.formula for item in species) != sorted(expected):
        return []
    return [list(item) for item in args.get("products") or []]


BUILDERS = {
    "exchange": build_exchange,
    "neutralization": build_neutralization,
    "acid_salt": build_acid_salt,
    "deprotonate": build_deprotonate,
    "metal_acid_hydrogen": build_metal_acid_hydrogen,
    "metal_nitric": build_metal_nitric,
    "metal_conc_sulfuric": build_metal_conc_sulfuric,
    "acid_oxide": build_acid_oxide,
    "oxide_oxidized": build_oxide_oxidized,
    "basic_oxide_water": build_basic_oxide_water,
    "acidic_oxide_water": build_acidic_oxide_water,
    "oxide_oxide": build_oxide_oxide,
    "acidic_oxide_base": build_acidic_oxide_base,
    "binary": build_binary,
    "hydroxide_heat": build_hydroxide_heat,
    "carbonate_heat": build_carbonate_heat,
    "bicarbonate_heat": build_bicarbonate_heat,
    "nitrate_heat": build_nitrate_heat,
    "ammonium_heat": build_ammonium_heat,
    "electrolysis_melt": build_electrolysis_melt,
    "electrolysis_solution": build_electrolysis_solution,
    "halogen_displace": build_halogen_displace,
    "metal_displace": build_metal_displace,
    "fe3_reduced": build_fe3_reduced,
    "reduce_oxide": build_reduce_oxide,
    "amphoteric_alkali": build_amphoteric_alkali,
    "amphoteric_metal": build_amphoteric_metal,
    "nonmetal_oxidation": build_nonmetal_oxidation,
    "halide_sulfuric": build_halide_sulfuric,
    "halogen_alkali": build_halogen_alkali,
    "no2_water": build_no2_water,
    "no2_base": build_no2_base,
    "chlorate_heat": build_chlorate_heat,
    "permanganate_heat": build_permanganate_heat,
    "nitride_water": build_nitride_water,
    "sulfide_roast": build_sulfide_roast,
    "metal_co2": build_metal_co2,
    "metal_water": build_metal_water,
    "so2_halogen_water": build_so2_halogen_water,
    "unstable_acid": build_unstable_acid,
    "ammonia_acid": build_ammonia_acid,
    "reducing_salt": build_reducing_salt,
    "halogen_water": build_halogen_water,
    "hydride_water": build_hydride_water,
    "h2s_oxygen": build_h2s_oxygen,
    "hx_oxygen": build_hx_oxygen,
    "halide_hydrolysis": build_halide_hydrolysis,
    "peroxide_reaction": build_peroxide_reaction,
    "carbon_gases": build_carbon_gases,
    "lab_chlorine": build_lab_chlorine,
    "electrolysis_aqueous": build_electrolysis_aqueous,
    "fe_hydroxide_air": build_fe_hydroxide_air,
    "permanganate": build_permanganate,
    "amphoteric_salt": build_amphoteric_salt,
    "fixed": build_fixed,
}


def _condition_allowed(rule: dict, assigned: list[Species], condition: str) -> bool:
    generate = rule.get("generate") or {}
    if condition not in (generate.get("conditions") or ["NONE"]):
        return False
    specific = generate.get("condition_if") or {}
    for item in assigned:
        allowed = specific.get(item.formula)
        if allowed and condition not in allowed:
            return False
    return True


def _assignments(rule: dict, reactants: list[Species], catalog: Catalog):
    slots = (rule.get("generate") or {}).get("slots") or []
    if len(slots) != len(reactants):
        return
    seen = set()
    for perm in permutations(reactants):
        key = tuple(item.formula for item in perm)
        if key in seen:
            continue
        if all(slot_ok(item, slot, catalog) for item, slot in zip(perm, slots)):
            seen.add(key)
            yield list(perm)


def propose(
    reactant_formulas: list[str],
    condition: str,
    rules: list[dict],
    catalog: Catalog,
    rejected: set[tuple] | None = None,
) -> list[dict]:
    """Sinh mọi phản ứng cân bằng được từ đúng các chất tham gia và điều kiện đã cho."""
    species = []
    for formula in reactant_formulas:
        item = catalog.get(formula)
        if item is None:
            return []
        species.append(item)
    rejected = rejected or set()
    found: dict[tuple, dict] = {}
    ordered_rules = sorted(rules, key=lambda rule: -int(rule.get("priority") or 0))
    for rule in ordered_rules:
        generate = rule.get("generate") or {}
        builder = BUILDERS.get(generate.get("builder") or "")
        if builder is None:
            continue
        for assigned in _assignments(rule, species, catalog):
            if not _condition_allowed(rule, assigned, condition):
                continue
            try:
                options = builder(assigned, catalog, generate.get("args") or {}, condition)
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                continue
            for products in options:
                products = _collapse(products)
                if not products or sorted(products) == sorted(reactant_formulas):
                    continue
                signature = reaction_signature(reactant_formulas, products, condition)
                if signature in rejected or signature in found:
                    continue
                try:
                    balanced = balance_formulas(list(reactant_formulas), list(products))
                except BalanceError:
                    continue
                found[signature] = _record(rule, reactant_formulas, balanced, condition)
    return list(found.values())


def reaction_signature(reactants: list[str], products: list[str], condition: str) -> tuple:
    return (condition or "NONE", tuple(sorted(reactants)), tuple(sorted(products)))


def _record(rule: dict, reactants: list[str], balanced: dict, condition: str) -> dict:
    reaction_type = rule.get("type") or "khac"
    return {
        "id": rule["id"],
        "rule_id": rule["id"],
        "rule_text": f"{rule.get('if_text', '')} → {rule.get('then_text', '')}",
        "type": reaction_type,
        "type_label": REACTION_TYPE_LABELS.get(reaction_type, "Phản ứng"),
        "reactants": list(reactants),
        "products": list(balanced["products"]),
        "coefficients": list(balanced["coefficients"]),
        "condition": condition or "NONE",
        "priority": int(rule.get("priority") or 0),
    }


def generate_pool_reactions(
    catalog: Catalog,
    rules: list[dict],
    pool: set[str],
    rejected: set[tuple] | None = None,
) -> list[dict]:
    """Mọi phản ứng mà chất phụ nằm trong kho thuốc thử. Dùng cho tìm chuỗi."""
    rejected = rejected or set()
    pool_species = [catalog.species[formula] for formula in pool if formula in catalog.species]
    all_species = list(catalog.species.values())
    by_slot: dict[int, list[list[Species]]] = {}
    reactions: dict[tuple, dict] = {}
    for rule in rules:
        generate = rule.get("generate") or {}
        builder_name = generate.get("builder") or ""
        if builder_name not in BUILDERS:
            continue
        slots = generate.get("slots") or []
        conditions = list(generate.get("search_conditions") or generate.get("conditions") or ["NONE"])
        cache_key = id(rule)
        if cache_key not in by_slot:
            by_slot[cache_key] = [[item for item in all_species if slot_ok(item, slot, catalog)] for slot in slots]
            by_slot[cache_key + 1] = [[item for item in pool_species if slot_ok(item, slot, catalog)] for slot in slots]
        matched = by_slot[cache_key]
        pooled = by_slot[cache_key + 1]
        if any(len(bucket) == 0 for bucket in pooled) and len(slots) > 1:
            # Vẫn thử nếu chất chính không nằm trong kho nhưng chất phụ thì có.
            pass
        if len(slots) == 1:
            groups = [[item] for item in matched[0]]
        else:
            groups = _pool_groups(matched, pooled)
        for group in groups:
            formulas = [item.formula for item in group]
            if len(set(formulas)) != len(formulas) and len(slots) > 1:
                continue
            for condition in conditions:
                if not _condition_allowed(rule, group, condition):
                    continue
                for record in propose(formulas, condition, [rule], catalog, rejected):
                    signature = reaction_signature(record["reactants"], record["products"], condition)
                    current = reactions.get(signature)
                    if current is None or record["priority"] > current["priority"]:
                        reactions[signature] = record
    return list(reactions.values())


def _pool_groups(matched: list[list[Species]], pooled: list[list[Species]]) -> list[list[Species]]:
    """Một chất bất kỳ đứng ở một ô, các ô còn lại lấy từ kho thuốc thử."""
    groups = []
    width = len(matched)
    for main_index in range(width):
        others = [pooled[index] for index in range(width) if index != main_index]
        if any(not bucket for bucket in others):
            continue
        mains = matched[main_index]
        # Giới hạn tổ hợp: ô thuốc thử đã được thu hẹp bởi điều kiện luật.
        if width == 2:
            other_index = 1 - main_index
            for main in mains:
                for aux in pooled[other_index]:
                    group = [None, None]
                    group[main_index] = main
                    group[other_index] = aux
                    groups.append(group)
        elif width == 3:
            indexes = [index for index in range(3) if index != main_index]
            for main in mains:
                for first in pooled[indexes[0]]:
                    for second in pooled[indexes[1]]:
                        group = [None, None, None]
                        group[main_index] = main
                        group[indexes[0]] = first
                        group[indexes[1]] = second
                        groups.append(group)
        elif width == 4:
            indexes = [index for index in range(4) if index != main_index]
            for main in mains:
                for first in pooled[indexes[0]]:
                    for second in pooled[indexes[1]]:
                        for third in pooled[indexes[2]]:
                            group = [None, None, None, None]
                            group[main_index] = main
                            group[indexes[0]] = first
                            group[indexes[1]] = second
                            group[indexes[2]] = third
                            groups.append(group)
    return groups


def index_rules_by_builder(rules: list[dict]) -> dict[str, list[dict]]:
    grouped = defaultdict(list)
    for rule in rules:
        builder = (rule.get("generate") or {}).get("builder")
        if builder:
            grouped[builder].append(rule)
    return grouped
