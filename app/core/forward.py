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
    # Không nêu tỉ lệ mol thì lấy muối trung hòa, là phương án ghi trước.
    return results[:1]


def build_acid_salt(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    """Axit nhiều nấc proton hóa một nấc muối của gốc đa bazơ. HCl không tạo M(HCO3)2."""
    acid = _pick(species, "acid")
    salt = _pick(species, "salt")
    if acid is None or salt is None or salt.anion is None or salt.cation is None or acid.anion is None:
        return []
    if acid.formula not in {"H2SO4", "H2SO3", "H2S", "H3PO4", "H3PO3", "H2CO3"}:
        return []
    if salt.anion.formula == "SO4" and acid.formula != "H2SO4":
        return []
    if salt.anion.formula in {"CO3", "HCO3", "SO3", "S"} and acid.formula in {"HCl", "HBr", "HI", "HNO3"}:
        return []
    ladder = {
        "CO3": ["HCO3"],
        "SO3": ["HSO3"],
        "SO4": ["HSO4"],
        "S": ["HS"],
        "PO4": ["H2PO4"],
        "HPO4": ["H2PO4"],
    }
    results = []
    for anion in ladder.get(salt.anion.formula, []):
        acid_salt = catalog.salt(salt.cation.formula, salt.cation.charge, anion)
        partner = _ion_product(catalog, salt.cation.formula, salt.cation.charge, acid.anion.formula)
        if acid_salt and partner:
            results.append(_collapse([acid_salt, *partner]))
            break
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
    if (
        salt.cation.formula in {"Na", "K"}
        and base.cation.formula == "Ca"
        and anion in {"CO3", "HPO4", "PO4"}
    ):
        earth = catalog.salt(base.cation.formula, base.cation.charge, anion)
        alkali = catalog.salt(salt.cation.formula, salt.cation.charge, "OH")
        if earth and alkali:
            return [[earth, alkali, "H2O"]]
    if other and own and salt.cation.formula != base.cation.formula:
        results.append(_collapse([other, own, "H2O"]))
    return results[:1]


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
    return results[:1]


def build_metal_conc_sulfuric(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    metal = _pick(species, "metal")
    if metal is None or metal.element is None:
        return []
    valence = _valence_choice(catalog, metal.element, "high")
    salt = catalog.salt(metal.element, valence, "SO4") if valence else None
    if not salt:
        return []
    # H2SO4 đặc không sinh H2S trong bộ sản phẩm chọn cho lời giải. Sản phẩm khử đại diện là SO2.
    return [[salt, "SO2", "H2O"]]


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
    acids = _anhydride_acids(oxide, catalog)
    common = {"H3PO4", "H2SO4", "H2SO3", "HNO3", "H2CO3", "H3BO3", "H2SiO3", "H2CrO4", "HClO", "HClO3"}
    preferred = [acid for acid in acids if acid.formula in common]
    element = oxide.element
    matched = [acid for acid in acids if element and acid.composition.get(element) == oxide.composition.get(element)]
    chosen = preferred or matched or acids
    return [[chosen[0].formula]] if chosen else []


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
    common = {"H3PO4", "H2SO4", "H2SO3", "H2CO3", "H3BO3", "H2SiO3", "H2CrO4"}
    acids = _anhydride_acids(oxide, catalog)
    ordered = [acid for acid in acids if acid.formula in common] + [acid for acid in acids if acid.formula not in common]
    for acid in ordered:
        if acid.anion is None:
            continue
        full = catalog.salt(base.cation.formula, base.cation.charge, acid.anion.formula)
        if full:
            return [[full, "H2O"]]
    return []


_OXIDE_PREFERRED = {
    "Fe": "Fe3O4",
    "Cr": "Cr2O3",
    "Mn": "MnO2",
    "Pb": "PbO",
    "Cu": "CuO",
    "Sn": "SnO2",
    "Al": "Al2O3",
    "Mg": "MgO",
    "Zn": "ZnO",
    "Ca": "CaO",
    "Na": "Na2O2",
    "K": "KO2",
}


def _binary_formulas(left: Species, right: Species, catalog: Catalog) -> list[str]:
    elements = {left.element, right.element}
    banned = {left.formula, right.formula}
    found = []
    for candidate in catalog.species.values():
        if candidate.formula in banned:
            continue
        if set(candidate.composition) <= elements and left.element in candidate.composition and right.element in candidate.composition:
            found.append(candidate.formula)
    return found


def _halide_by_valence(formulas: list[str], metal: str, catalog: Catalog, high: bool) -> str | None:
    ranked = []
    for formula in formulas:
        species = catalog.get(formula)
        if species and species.cation and species.cation.formula == metal:
            ranked.append((species.cation.charge, formula))
    if not ranked:
        return sorted(formulas)[0] if formulas else None
    ranked.sort()
    return ranked[-1 if high else 0][1]


def build_binary(species: list[Species], catalog: Catalog, _args: dict, condition: str) -> list[list[str]]:
    """Một hợp chất nhị tố. Halogen mạnh cho hóa trị cao, lưu huỳnh với sắt cho FeS, oxi theo oxit thường gặp."""
    if len(species) != 2:
        return []
    left, right = species
    if left.kind not in {"metal", "nonmetal"} or right.kind not in {"metal", "nonmetal"}:
        return []
    if not left.element or not right.element or left.element == right.element:
        return []
    names = {left.formula, right.formula}
    if "O2" in names and {left.element, right.element}.intersection({"Au", "Pt"}):
        return []
    if names == {"H2", "O2"}:
        return [["H2O"]] if "H2O" in catalog.compounds else []
    if names == {"N2", "O2"}:
        # Dữ liệu ghi tia lửa điện bằng điều kiện đun. Không sinh NO ở điều kiện thường.
        if condition in {"HEAT", "OTHER"} and "NO" in catalog.compounds:
            return [["NO"]]
        return []
    formulas = _binary_formulas(left, right, catalog)
    if not formulas:
        return []
    metal = left.element if left.kind == "metal" else right.element if right.kind == "metal" else None
    nonmetal = left.element if left.kind == "nonmetal" else right.element if right.kind == "nonmetal" else None
    if names == {"C", "O2"} and "CO2" in formulas:
        return [["CO2"]]
    if names == {"S", "O2"} and "SO2" in formulas:
        return [["SO2"]]
    if names == {"P", "O2"}:
        for formula in ("P2O5", "P4O10"):
            if formula in formulas:
                return [[formula]]
    if metal and nonmetal == "O":
        preferred = _OXIDE_PREFERRED.get(metal)
        if preferred in formulas:
            return [[preferred]]
        chosen = _halide_by_valence(formulas, metal, catalog, high=True)
        return [[chosen]] if chosen else []
    if metal and nonmetal in {"Cl", "Br"}:
        chosen = _halide_by_valence(formulas, metal, catalog, high=True)
        return [[chosen]] if chosen else []
    if metal and nonmetal == "I":
        chosen = _halide_by_valence(formulas, metal, catalog, high=False)
        return [[chosen]] if chosen else []
    if metal and nonmetal == "S":
        if metal == "Fe" and "FeS" in formulas:
            return [["FeS"]]
        if metal == "Cu" and "CuS" in formulas:
            return [["CuS"]]
        chosen = _halide_by_valence(formulas, metal, catalog, high=False)
        return [[chosen]] if chosen else []
    if len(formulas) == 1:
        return [[formulas[0]]]
    return [[sorted(formulas)[0]]]


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
    groups = set((catalog.elements.get(cation) or {}).get("groups") or [])
    if cation == "Li" or "kiem_tho" in groups or (
        _activity_at_least(catalog, cation, "Mg") and _activity_at_most(catalog, cation, "Cu")
    ):
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


def _prefer_hydroxo(formulas: list[str]) -> str | None:
    if not formulas:
        return None
    hydroxy = [formula for formula in formulas if "(OH)" in formula or "[OH]" in formula]
    pool = hydroxy or formulas
    return sorted(pool, key=lambda formula: (-formula.count("OH"), formula))[0]


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
    chosen = _prefer_hydroxo(_complexes(catalog, metal or "", base.cation.formula, {base.formula, amph.formula}))
    if not chosen:
        return []
    return [[chosen], [chosen, "H2O"]]


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
    chosen = _prefer_hydroxo(_complexes(catalog, salt.cation.formula, base.cation.formula, {salt.formula, base.formula}))
    if not chosen:
        return []
    return [[chosen, partner], [chosen, partner, "H2O"]]


def build_amphoteric_metal(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    metal = _pick(species, "metal")
    base = _pick(species, "base")
    if metal is None or base is None or metal.element is None or base.cation is None:
        return []
    if metal.element not in AMPHOTERIC_METALS:
        return []
    banned = {item.formula for item in species}
    chosen = _prefer_hydroxo(_complexes(catalog, metal.element, base.cation.formula, banned))
    return [[chosen, "H2"]] if chosen else []


def build_nonmetal_oxidation(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    simple = next((item for item in species if item.kind == "nonmetal"), None)
    acid = _pick(species, "acid")
    if simple is None or acid is None or simple.element not in {"C", "S", "P"}:
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
    common = {"H3PO4", "H2SO4", "H2SO3", "SO2", "CO2"}
    ordered = [item for item in chosen if item.formula in common] or chosen[:1]
    candidate = ordered[0]
    reduced = "NO2" if acid.formula == "HNO3" else "SO2"
    product = candidate.formula
    if acid.formula == "H2SO4" and product == "H2SO4":
        return [["SO2", "H2O"]]
    extras = [reduced, "H2O"]
    if product == "H2CO3":
        return [_collapse(["CO2", "H2O", *extras])]
    if product == "H2SO3":
        return [_collapse(["SO2", "H2O", *extras])]
    return [_collapse([product, *extras])]


def build_halide_sulfuric(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    salt = _pick(species, "salt")
    if salt is None or salt.anion is None or salt.cation is None or salt.anion.formula not in {"Cl", "Br", "I"}:
        return []
    if salt.cation.formula == "Fe" and salt.cation.charge < ( _valence_choice(catalog, "Fe", "high") or 3):
        return []
    hydrogen = {"Cl": "HCl", "Br": "HBr", "I": "HI"}[salt.anion.formula]
    product = catalog.salt(salt.cation.formula, salt.cation.charge, "HSO4")
    if product is None:
        product = catalog.salt(salt.cation.formula, salt.cation.charge, "SO4")
    return [[product, hydrogen]] if product else []


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
    hot = condition in {"HEAT", "CONC_HEAT", "DILUTE_HEAT", "HEAT_CATALYST", "HEAT_LIGHT"}
    partner = catalog.salt(cation, charge, halate if hot else hypo)
    if salt_halide and partner:
        return [[salt_halide, partner, "H2O"]]
    return []


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
    if chloride and perchlorate:
        return [[chloride, perchlorate]]
    return [[chloride, "O2"]] if chloride else []


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
    if metal in {"Ag", "Hg", "Au", "Pt"} and metal in catalog.compounds:
        return [[metal, "SO2"]]
    oxide = None
    if metal == "Fe":
        oxide = "Fe2O3" if "Fe2O3" in catalog.compounds else None
    preferred = _OXIDE_PREFERRED.get(metal) if metal != "Fe" else None
    if oxide is None and preferred in catalog.compounds:
        oxide = preferred
    if oxide is None and charge:
        oxide = catalog.oxide(metal, charge)
    high = _valence_choice(catalog, metal, "high")
    if oxide is None and high:
        oxide = catalog.oxide(metal, high)
    return [[oxide, "SO2"]] if oxide else []


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
    if element == "Fe" and "Fe3O4" in catalog.compounds:
        return [["Fe3O4", "H2"]]
    if element in {"Mg", "Al", "Zn"} or element in AMPHOTERIC_METALS:
        hydroxide = catalog.salt(element, valence, "OH") if valence else None
        return [[hydroxide, "H2"]] if hydroxide else []
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
    if anion in {"CO3", "HCO3"}:
        return [[salt, reduced, "CO2", "H2O"]]
    if anion == "S":
        sulfur_count = other.composition.get("S", 0)
        metal_count = other.composition.get(metal, 0)
        sulfate = catalog.salt(metal, high, "SO4")
        valence_rises = charge is not None and high > charge
        if acid.formula == "HNO3":
            if metal == "Fe" or sulfur_count > metal_count or not valence_rises:
                return [[salt, "H2SO4", reduced, "H2O"]]
            if sulfate:
                return [[salt, sulfate, reduced, "H2O"]]
            return [[salt, reduced, "H2O"]]
        products = [salt, "SO2", "H2O"]
        if not valence_rises and sulfur_count <= metal_count and metal != "Fe":
            products = [salt, "SO2", "S", "H2O"]
        return [products]
    if other.cation and charge is not None and high > charge:
        if anion in {"Cl", "Br", "I"}:
            hydrogen = {"Cl": "HCl", "Br": "HBr", "I": "HI"}[anion]
            return [[salt, reduced, hydrogen, "H2O"]]
        return [[salt, reduced, "H2O"]]
    return []


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
    fixed = {
        "PCl3": ["H3PO3", "HCl"],
        "PCl5": ["H3PO4", "HCl"],
        "PBr3": ["H3PO3", "HBr"],
        "PBr5": ["H3PO4", "HBr"],
    }
    if compound.formula in fixed and all(item in catalog.compounds for item in fixed[compound.formula]):
        return [fixed[compound.formula]]
    acids = [
        candidate.formula
        for candidate in catalog.species.values()
        if candidate.kind == "acid" and element in candidate.composition and set(candidate.composition) <= {element, "O", "H"}
    ]
    if acids:
        return [[sorted(acids)[0], hydrogen]]
    oxides = [
        candidate.formula
        for candidate in catalog.species.values()
        if candidate.kind == "oxide" and set(candidate.composition) <= {element, "O"} and element in candidate.composition
    ]
    return [[oxides[0], hydrogen]] if oxides else []


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
        return [["CO", "H2"]]
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
    products = oxidized + ["K2SO4", "MnSO4"]
    if "H2O" not in formulas:
        products.append("H2O")
    return [products]


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


def build_phosphate_acid(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    """Axit mạnh đưa muối photphat tới đihiđrophotphat, đúng một bậc tỉ lệ trong SGK."""
    acid = _pick(species, "acid")
    salt = _pick(species, "salt")
    if acid is None or salt is None or salt.anion is None or salt.cation is None or acid.anion is None:
        return []
    if salt.anion.formula not in {"PO4", "HPO4"} or acid.formula not in {"HCl", "HBr", "HI", "HNO3", "H2SO4"}:
        return []
    acid_salt = catalog.salt(salt.cation.formula, salt.cation.charge, "H2PO4")
    partner = _ion_product(catalog, salt.cation.formula, salt.cation.charge, acid.anion.formula)
    if acid_salt and partner:
        return [_collapse([acid_salt, *partner])]
    return []


def build_chromate_equilibrium(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    acid = _pick(species, "acid")
    base = _pick(species, "base")
    salt = _pick(species, "salt")
    if salt is None or salt.cation is None or salt.anion is None:
        return []
    if acid and salt.anion.formula == "CrO4" and acid.formula in {"H2SO4", "HCl", "HNO3"}:
        dichromate = catalog.salt(salt.cation.formula, salt.cation.charge, "Cr2O7")
        partner = catalog.salt(salt.cation.formula, salt.cation.charge, acid.anion.formula if acid.anion else "")
        if dichromate and partner:
            return [[dichromate, partner, "H2O"]]
    if base and salt.anion.formula == "Cr2O7" and base.cation and base.formula in {"NaOH", "KOH", "Ba(OH)2"}:
        chromate = catalog.salt(base.cation.formula, base.cation.charge, "CrO4")
        if chromate:
            return [[chromate, "H2O"]]
    return []


def build_chlorate_acid(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    salt = _pick(species, "salt")
    acid = _pick(species, "acid")
    if salt is None or acid is None or acid.formula != "HCl" or salt.anion is None or salt.anion.formula != "ClO3":
        return []
    if salt.cation is None:
        return []
    chloride = catalog.salt(salt.cation.formula, salt.cation.charge, "Cl")
    return [[chloride, "Cl2", "H2O"]] if chloride else []


def build_so2_oxidation(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    if formulas == {"SO2", "O2"}:
        return [["SO3"]]
    return []


def build_ammonia_burn(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    if formulas == {"NH3", "O2"}:
        return [["N2", "H2O"]]
    return []


def build_salt_hydrolysis(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    """Muối cation axit yếu bị thủy phân khi gặp CO3, S hoặc NH3."""
    if not any(item.formula == "H2O" for item in species):
        return []
    salt = next((item for item in species if item.kind == "salt" and item.cation and item.anion), None)
    if salt is None or salt.cation is None or salt.anion is None:
        return []
    cation, charge, anion = salt.cation.formula, salt.cation.charge, salt.anion.formula
    hydroxide = catalog.salt(cation, charge, "OH")
    if hydroxide is None:
        return []
    if any(item.formula == "NH3" for item in species) and cation in {"Al", "Fe", "Zn", "Cu", "Cr"}:
        ammonium = catalog.salt("NH4", 1, anion)
        return [[hydroxide, ammonium]] if ammonium else []
    partner = next((item for item in species if item.kind == "salt" and item is not salt and item.cation and item.anion), None)
    if partner is None or partner.anion is None or partner.cation is None:
        return []
    if cation not in {"Al", "Fe", "Cr"} or charge != 3:
        return []
    other = catalog.salt(partner.cation.formula, partner.cation.charge, anion)
    if partner.anion.formula == "CO3" and other:
        return [[hydroxide, "CO2", other]]
    if partner.anion.formula == "S" and other:
        return [[hydroxide, "H2S", other]]
    return []


def build_bisulfate(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    salts = [item for item in species if item.kind == "salt" and item.anion and item.cation]
    if len(salts) != 2:
        return []
    bisulfate = next((item for item in salts if item.anion and item.anion.formula == "HSO4"), None)
    other = next((item for item in salts if item is not bisulfate), None)
    if bisulfate is None or other is None or other.anion is None or other.cation is None or bisulfate.cation is None:
        return []
    sulfate = catalog.salt(bisulfate.cation.formula, bisulfate.cation.charge, "SO4")
    if other.cation.formula == "Ba" and other.anion.formula in {"Cl", "NO3"} and sulfate:
        halide = catalog.salt(bisulfate.cation.formula, bisulfate.cation.charge, other.anion.formula)
        acid = {"Cl": "HCl", "NO3": "HNO3"}.get(other.anion.formula)
        if halide and acid:
            return [["BaSO4", halide, acid]]
    if other.anion.formula in {"HCO3", "CO3"} and sulfate:
        return [[sulfate, "CO2", "H2O"]]
    return []


def build_peroxide_oxidant(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    if not any(item.formula == "H2O2" for item in species):
        return []
    formulas = {item.formula for item in species}
    if "SO2" in formulas:
        return [["H2SO4"]]
    if "H2S" in formulas:
        return [["S", "H2O"]]
    iron = next((item for item in species if item.cation and item.cation.formula == "Fe" and item.cation.charge == 2 and item.anion), None)
    if iron and iron.anion and any(item.kind == "acid" for item in species):
        high = catalog.salt("Fe", 3, iron.anion.formula)
        if high:
            return [[high, "H2O"]]
    iodide = next((item for item in species if item.anion and item.anion.formula == "I" and item.cation), None)
    acid = _pick(species, "acid")
    if iodide and iodide.cation and acid and acid.anion:
        halogen = "I2"
        salt = catalog.salt(iodide.cation.formula, iodide.cation.charge, acid.anion.formula)
        if salt:
            return [[halogen, salt, "H2O"]]
    return []


def build_halide_phosphoric(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    acid = _pick(species, "acid")
    salt = _pick(species, "salt")
    if acid is None or salt is None or acid.formula != "H3PO4" or salt.anion is None or salt.cation is None:
        return []
    if salt.anion.formula not in {"Cl", "Br", "I"}:
        return []
    hydrogen = {"Cl": "HCl", "Br": "HBr", "I": "HI"}[salt.anion.formula]
    phosphate = catalog.salt(salt.cation.formula, salt.cation.charge, "H2PO4")
    return [[phosphate, hydrogen]] if phosphate else []


def build_nitrate_sulfuric(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    salt = _pick(species, "salt")
    if salt is None or salt.anion is None or salt.anion.formula != "NO3" or salt.cation is None:
        return []
    if not any(item.formula == "H2SO4" for item in species):
        return []
    bisulfate = catalog.salt(salt.cation.formula, salt.cation.charge, "HSO4")
    sulfate = catalog.salt(salt.cation.formula, salt.cation.charge, "SO4")
    sulfate_species = catalog.get(sulfate) if sulfate else None
    if sulfate and sulfate_species and sulfate_species.solubility == "khong_tan":
        return [[sulfate, "HNO3"]]
    return [[bisulfate, "HNO3"]] if bisulfate else []


def build_iodide_reduction(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    if not any(item.formula == "HI" for item in species):
        return []
    other = next((item for item in species if item.formula != "HI"), None)
    if other is None:
        return []
    metal = other.element or (other.cation.formula if other.cation else None)
    if metal == "Fe":
        iodide = catalog.salt("Fe", 2, "I")
        return [[iodide, "I2", "H2O"]] if iodide else []
    if metal == "Cu" or other.formula == "CuO":
        iodide = "CuI" if "CuI" in catalog.compounds else catalog.salt("Cu", 1, "I")
        return [[iodide, "I2", "H2O"]] if iodide else []
    return []


def build_complex_acid(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    acid = _pick(species, "acid")
    compound = next((item for item in species if item is not acid), None)
    if acid is None or compound is None or acid.formula not in {"HCl", "H2SO4", "HNO3"} or acid.anion is None:
        return []
    composition = compound.composition
    metal = next((element for element in ("Al", "Zn", "Cr", "Be", "Sn", "Pb") if element in composition), None)
    alkali = next((element for element in ("Na", "K") if element in composition), None)
    if metal is None or alkali is None:
        return []
    valence = _valence_choice(catalog, metal, "high") or 3
    hydroxide = catalog.salt(metal, valence, "OH")
    salt = catalog.salt(alkali, 1, acid.anion.formula)
    if hydroxide and salt:
        return [[hydroxide, salt, "H2O"], [hydroxide, salt]]
    return []


def build_silicate_co2(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    if "CO2" in formulas and "H2O" in formulas and formulas & {"Na2SiO3", "K2SiO3"}:
        alkali = "Na2CO3" if "Na2SiO3" in formulas else "K2CO3"
        return [["H2SiO3", alkali]]
    return []


def build_silica_carbonate(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    if "SiO2" in formulas and "Na2CO3" in formulas:
        return [["Na2SiO3", "CO2"]]
    if "SiO2" in formulas and "K2CO3" in formulas:
        return [["K2SiO3", "CO2"]]
    return []


def build_phosphide_water(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    compound = next((item for item in species if item.formula != "H2O"), None)
    if compound is None or "P" not in compound.composition or len(compound.composition) != 2:
        return []
    metal = next(element for element in compound.composition if element != "P")
    if not _element_is_metal(catalog, metal):
        return []
    valence = _valence_choice(catalog, metal, "low") or _valence_choice(catalog, metal, "high")
    hydroxide = catalog.salt(metal, valence, "OH") if valence else None
    return [[hydroxide, "PH3"]] if hydroxide else []


def build_peroxide_acid(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    acid = _pick(species, "acid")
    other = next((item for item in species if item is not acid), None)
    if acid is None or other is None or acid.formula != "H2SO4" or acid.anion is None:
        return []
    if other.formula == "BaO2":
        return [["BaSO4", "H2O2"]]
    if other.cation and other.formula in {"Na2O2", "K2O2"}:
        sulfate = catalog.salt(other.cation.formula, other.cation.charge, "SO4")
        return [[sulfate, "H2O2"]] if sulfate else []
    return []


def build_halogen_nitric(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    table = {"Cl2": "HClO3", "Br2": "HBrO3", "I2": "HIO3"}
    for halogen, acid in table.items():
        if formulas == {halogen, "HNO3"}:
            return [[acid, "NO2", "H2O"]]
    return []


def build_cyanide_complex(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    """Muối kim loại chuyển vị với KCN hoặc KSCN nếu phức đã có trong từ điển chất."""
    ligand_salt = next((item for item in species if item.anion and item.anion.formula in {"CN", "SCN"} and item.cation), None)
    metal_salt = next((item for item in species if item is not ligand_salt and item.cation and item.anion), None)
    if ligand_salt is None or metal_salt is None or ligand_salt.cation is None or metal_salt.cation is None:
        return []
    metal = metal_salt.cation.formula
    alkali = ligand_salt.cation.formula
    ligand = ligand_salt.anion.formula
    found = []
    for candidate in catalog.species.values():
        elements = set(candidate.composition)
        if metal in elements and ligand[0] in elements and elements <= {metal, alkali, "C", "N", "S", "Fe"}:
            found.append(candidate.formula)
    if not found:
        return []
    complex_formula = sorted(found, key=len)[0]
    partner = catalog.salt(alkali, ligand_salt.cation.charge, metal_salt.anion.formula)
    if partner:
        return [[complex_formula, partner]]
    return [[complex_formula]]


def build_complex_carbon_dioxide(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    compound = next((item for item in species if "Al" in item.composition and "Na" in item.composition), None)
    if compound is None or not any(item.formula == "CO2" for item in species):
        return []
    hydroxide = catalog.salt("Al", 3, "OH")
    return [[hydroxide, "NaHCO3"]] if hydroxide else []


def build_iron_silver(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    iron = next((item for item in species if item.cation and item.cation.formula == "Fe" and item.cation.charge == 2), None)
    silver = next((item for item in species if item.cation and item.cation.formula == "Ag"), None)
    if iron is None or silver is None or iron.anion is None:
        return []
    oxidized = catalog.salt("Fe", 3, iron.anion.formula)
    return [[oxidized, "Ag"]] if oxidized else []


def build_so2_no2(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    if formulas == {"SO2", "NO2", "H2O"}:
        return [["H2SO4", "NO"]]
    return []


def build_hydride_burn(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    table = {"PH3": "P2O5", "AsH3": "As2O3", "SbH3": "Sb2O3", "H2Se": "SeO2", "H2Te": "TeO2"}
    hydride = next((item for item in species if item.formula in table), None)
    if hydride is None or not any(item.formula == "O2" for item in species):
        return []
    return [[table[hydride.formula], "H2O"]]


def build_phosphorus_water(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    if formulas == {"P", "H2O"}:
        return [["H3PO3", "H2"]]
    return []


def build_phosphorus_halide(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    if formulas == {"PCl3", "Cl2"}:
        return [["PCl5"]]
    if formulas == {"PBr3", "Br2"}:
        return [["PBr5"]]
    return []


def build_ammonia_oxide(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    if formulas == {"NH3", "CuO"}:
        return [["Cu", "N2", "H2O"]]
    return []


def build_dichromate_redox(species: list[Species], catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    if "K2Cr2O7" not in formulas or "H2SO4" not in formulas:
        return []
    if "SO2" in formulas:
        return [["Cr2(SO4)3", "K2SO4", "H2O"]]
    iron = next((item for item in species if item.cation and item.cation.formula == "Fe" and item.cation.charge == 2), None)
    if iron and iron.anion and iron.anion.formula == "SO4":
        oxidized = catalog.salt("Fe", 3, "SO4")
        if oxidized:
            return [[oxidized, "Cr2(SO4)3", "K2SO4", "H2O"]]
    return []


def build_fluorine_water(species: list[Species], _catalog: Catalog, _args: dict, _condition: str) -> list[list[str]]:
    formulas = {item.formula for item in species}
    if formulas == {"F2", "H2O"}:
        return [["HF", "O2"]]
    return []


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
    "phosphate_acid": build_phosphate_acid,
    "chromate_equilibrium": build_chromate_equilibrium,
    "chlorate_acid": build_chlorate_acid,
    "so2_oxidation": build_so2_oxidation,
    "ammonia_burn": build_ammonia_burn,
    "salt_hydrolysis": build_salt_hydrolysis,
    "bisulfate": build_bisulfate,
    "peroxide_oxidant": build_peroxide_oxidant,
    "fluorine_water": build_fluorine_water,
    "halide_phosphoric": build_halide_phosphoric,
    "nitrate_sulfuric": build_nitrate_sulfuric,
    "iodide_reduction": build_iodide_reduction,
    "complex_acid": build_complex_acid,
    "silicate_co2": build_silicate_co2,
    "silica_carbonate": build_silica_carbonate,
    "phosphide_water": build_phosphide_water,
    "peroxide_acid": build_peroxide_acid,
    "halogen_nitric": build_halogen_nitric,
    "cyanide_complex": build_cyanide_complex,
    "complex_carbon_dioxide": build_complex_carbon_dioxide,
    "iron_silver": build_iron_silver,
    "so2_no2": build_so2_no2,
    "hydride_burn": build_hydride_burn,
    "phosphorus_water": build_phosphorus_water,
    "phosphorus_halide": build_phosphorus_halide,
    "ammonia_oxide": build_ammonia_oxide,
    "dichromate_redox": build_dichromate_redox,
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
                if set(products) & set(reactant_formulas):
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


def primary_candidate(candidates: list[dict]) -> dict | None:
    """Một bộ sản phẩm: ưu tiên luật cao hơn, rồi ít chất sản phẩm hơn, rồi thứ tự công thức."""
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            int(item.get("priority") or 0),
            -len(item["products"]),
            tuple(sorted(item["products"])),
        ),
    )


def reaction_signature(reactants: list[str], products: list[str], condition: str) -> tuple:
    return (condition or "NONE", tuple(sorted(reactants)), tuple(sorted(products)))


def _record(rule: dict, reactants: list[str], balanced: dict, condition: str) -> dict:
    reaction_type = rule.get("type") or "khac"
    record = {
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
    symbol = ((rule.get("generate") or {}).get("args") or {}).get("symbol")
    if symbol:
        record["condition_symbol"] = symbol
    return record


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
