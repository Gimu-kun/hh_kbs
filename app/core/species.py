"""Suy ra ion, gốc axit, hóa trị, số oxi hóa và tính tan từ công thức.

Nguồn dùng khi điền thuộc tính còn thiếu (không bịa số đo):

- Hóa trị: danh sách ``valence`` đã có của nguyên tố.
- Số oxi hóa: quy tắc SGK Hóa học 10 — tổng số oxi hóa bằng điện tích;
  O = -2 (peoxit -1); H = +1 (hiđrua kim loại -1); kim loại dương bằng điện tích ion.
- Gốc axit và điện tích ion: bảng gốc axit SGK (Cl-, SO4 2-, NO3-, CO3 2-, PO4 3-, ...).
- Tính tan: chỉ ghi đè khi dữ liệu đang là ``chua_ro``, theo bảng tính tan SGK
  (muối Na+/K+/NH4+ và nitrat tan; halogenua tan trừ Ag+, Pb2+, Hg2+;
  sunfat tan trừ Ba2+, Pb2+, Sr2+ và Ca2+/Ag+ ít tan; muối S2-, CO3 2-, PO4 3-, SO3 2-
  của kim loại khác kiềm và amoni không tan).
- Fe3O4 và Co3O4: SGK coi là oxit kép FeO·Fe2O3 và CoO·Co2O3.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# (ký hiệu gốc, thành phần, điện tích). Gốc dài hơn được thử trước khi so khớp.
ANIONS: tuple[tuple[str, dict[str, int], int], ...] = (
    ("P2O7", {"P": 2, "O": 7}, -4),
    ("Cr2O7", {"Cr": 2, "O": 7}, -2),
    ("H2PO4", {"H": 2, "P": 1, "O": 4}, -1),
    ("HPO4", {"H": 1, "P": 1, "O": 4}, -2),
    ("HCO3", {"H": 1, "C": 1, "O": 3}, -1),
    ("HSO4", {"H": 1, "S": 1, "O": 4}, -1),
    ("HSO3", {"H": 1, "S": 1, "O": 3}, -1),
    ("HS", {"H": 1, "S": 1}, -1),
    ("SO4", {"S": 1, "O": 4}, -2),
    ("SO3", {"S": 1, "O": 3}, -2),
    ("NO3", {"N": 1, "O": 3}, -1),
    ("NO2", {"N": 1, "O": 2}, -1),
    ("CO3", {"C": 1, "O": 3}, -2),
    ("PO4", {"P": 1, "O": 4}, -3),
    ("PO3", {"P": 1, "O": 3}, -1),
    ("SiO3", {"Si": 1, "O": 3}, -2),
    ("MnO4", {"Mn": 1, "O": 4}, -1),
    ("CrO4", {"Cr": 1, "O": 4}, -2),
    ("ClO4", {"Cl": 1, "O": 4}, -1),
    ("ClO3", {"Cl": 1, "O": 3}, -1),
    ("ClO2", {"Cl": 1, "O": 2}, -1),
    ("ClO", {"Cl": 1, "O": 1}, -1),
    ("BrO3", {"Br": 1, "O": 3}, -1),
    ("BrO", {"Br": 1, "O": 1}, -1),
    ("IO3", {"I": 1, "O": 3}, -1),
    ("SCN", {"S": 1, "C": 1, "N": 1}, -1),
    ("CN", {"C": 1, "N": 1}, -1),
    ("OH", {"O": 1, "H": 1}, -1),
    ("Cl", {"Cl": 1}, -1),
    ("Br", {"Br": 1}, -1),
    ("I", {"I": 1}, -1),
    ("F", {"F": 1}, -1),
    ("S", {"S": 1}, -2),
    ("Se", {"Se": 1}, -2),
    ("Te", {"Te": 1}, -2),
)

ANION_CHARGE = {name: charge for name, _composition, charge in ANIONS}
ANION_COMPOSITION = {name: composition for name, composition, _charge in ANIONS}

# Kim loại có oxit/hiđroxit lưỡng tính trong chương trình phổ thông.
AMPHOTERIC_METALS = {"Al", "Zn", "Be", "Cr", "Sn", "Pb"}

# Khí thường gặp khi xét điều kiện phản ứng trao đổi.
GAS_FORMULAS = {
    "H2", "O2", "N2", "Cl2", "F2", "Br2", "I2",
    "CO", "CO2", "SO2", "SO3", "NO", "NO2", "N2O", "NH3",
    "H2S", "HCl", "HBr", "HI", "HF", "PH3", "CH4", "C2H2",
}

WEAK_ELECTROLYTES = {
    "H2O", "NH3", "H2S", "H2CO3", "H2SO3", "H2SiO3", "H3PO4", "H3PO3",
    "HF", "HNO2", "HCN", "HClO", "H2S2O3",
}

# Axit mạnh SGK dùng để so sánh khi axit mạnh đẩy axit yếu.
STRONG_ACIDS = {"HCl", "HBr", "HI", "HNO3", "H2SO4", "HClO4", "HMnO4"}

# Muối Na+, K+, NH4+ tan; nitrat tan. Bảng tính tan SGK.
_ALWAYS_SOLUBLE_CATIONS = {"Na", "K", "NH4"}
_HALIDE_INSOLUBLE = {"Ag", "Pb", "Hg"}


@dataclass
class Ion:
    formula: str
    charge: int
    count: int
    role: str


@dataclass
class Species:
    formula: str
    compound: dict
    composition: dict[str, int]
    kind: str
    element: str | None = None
    cation: Ion | None = None
    anion: Ion | None = None
    oxidation: dict[str, int] = field(default_factory=dict)
    metal_valence: int | None = None
    oxide_kind: str | None = None
    solubility: str = "chua_ro"
    soluble_basis: str = ""
    mixed_valences: tuple[int, ...] = ()


def _subtract(composition: dict[str, int], part: dict[str, int], times: int) -> dict[str, int] | None:
    rest = dict(composition)
    for element, count in part.items():
        need = count * times
        have = rest.get(element, 0)
        if have < need:
            return None
        left = have - need
        if left:
            rest[element] = left
        else:
            rest.pop(element, None)
    return rest


def _is_metal(symbol: str, elements: dict[str, dict]) -> bool:
    element = elements.get(symbol)
    return bool(element and element.get("type") == "kim_loai")


def _valence_ok(symbol: str, charge: int, elements: dict[str, dict]) -> bool:
    valences = (elements.get(symbol) or {}).get("valence") or []
    if not valences:
        return charge > 0
    return charge in valences


def element_oxidation_states(element: dict) -> list[int]:
    """Gắn dấu cho hóa trị đã có, theo quy tắc SGK. Không thêm bậc oxi hóa mới."""
    symbol = element["symbol"]
    valences = [int(value) for value in (element.get("valence") or []) if int(value) > 0]
    if element.get("type") == "kim_loai":
        return valences
    if symbol == "O":
        return [-2, -1]
    if symbol == "H":
        return [1, -1]
    if symbol == "F":
        return [-1]
    if symbol == "C":
        # Hóa trị đã có là 2 và 4. Số -4 là số oxi hóa của C trong hidrocacbon (SGK), không phải số đo mới.
        return [-4, 2, 4]
    if not valences:
        return []
    lowest = min(valences)
    return sorted({-lowest, *valences})


def _central_oxidation(anion: str, charge: int) -> dict[str, int]:
    composition = dict(ANION_COMPOSITION.get(anion) or {})
    if not composition:
        return {}
    oxidation: dict[str, int] = {}
    accounted = charge
    if "O" in composition:
        oxidation["O"] = -2
        accounted -= -2 * composition.pop("O")
    if "H" in composition:
        oxidation["H"] = 1
        accounted -= 1 * composition.pop("H")
    if len(composition) == 1:
        element, count = next(iter(composition.items()))
        if count:
            oxidation[element] = accounted // count
    return oxidation


def solubility_from_ions(cation: str | None, anion: str | None) -> tuple[str, str] | None:
    """Bảng tính tan SGK. Trả về None nếu bảng không kết luận."""
    if not cation or not anion:
        return None
    if cation in _ALWAYS_SOLUBLE_CATIONS or anion == "NO3":
        return "tan", "Bảng tính tan SGK: muối của Na+, K+, NH4+ và mọi nitrat đều tan."
    if anion in {"Cl", "Br", "I"}:
        if cation in _HALIDE_INSOLUBLE:
            return "khong_tan", "Bảng tính tan SGK: AgCl, AgBr, AgI, PbCl2, PbBr2, PbI2 và muối Hg(I) tương ứng không tan."
        return "tan", "Bảng tính tan SGK: hầu hết clorua, bromua, iodua tan."
    if anion == "SO4":
        if cation in {"Ba", "Pb", "Sr", "Ra"}:
            return "khong_tan", "Bảng tính tan SGK: BaSO4, PbSO4, SrSO4 không tan."
        if cation in {"Ca", "Ag"}:
            return "it_tan", "Bảng tính tan SGK: CaSO4 và Ag2SO4 ít tan."
        return "tan", "Bảng tính tan SGK: hầu hết sunfat tan."
    if anion == "S":
        if cation in {"Na", "K", "NH4", "Ba", "Ca", "Sr"}:
            return "tan", "Bảng tính tan SGK: sunfua kim loại kiềm, kiềm thổ và amoni tan."
        if cation in {"Mg", "Al"}:
            return "phan_ung_nuoc", "SGK: MgS và Al2S3 bị thủy phân trong nước."
        return "khong_tan", "Bảng tính tan SGK: sunfua của hầu hết kim loại khác không tan."
    if anion in {"CO3", "PO4", "SO3", "SiO3"}:
        if cation in _ALWAYS_SOLUBLE_CATIONS:
            return "tan", "Bảng tính tan SGK: muối cacbonat, photphat, sunfit, silicat của Na+, K+, NH4+ tan."
        return "khong_tan", "Bảng tính tan SGK: muối cacbonat, photphat, sunfit, silicat của kim loại khác không tan."
    if anion == "OH":
        if cation in {"Na", "K", "Ba", "NH4"}:
            return "tan", "Bảng tính tan SGK: NaOH, KOH, Ba(OH)2 tan."
        if cation in {"Ca", "Sr"}:
            return "it_tan", "Bảng tính tan SGK: Ca(OH)2 và Sr(OH)2 ít tan."
        return "khong_tan", "Bảng tính tan SGK: hầu hết hiđroxit kim loại khác không tan."
    if anion in {"CrO4", "Cr2O7"}:
        if cation in {"Ba", "Pb", "Ag"}:
            return "khong_tan", "SGK: cromat của Ba2+, Pb2+, Ag+ không tan."
        if cation in _ALWAYS_SOLUBLE_CATIONS:
            return "tan", "SGK: cromat của Na+, K+, NH4+ tan."
    return None


def _fit_ions(composition: dict[str, int], elements: dict[str, dict]) -> tuple[Ion, Ion] | None:
    best = None
    best_key = None
    for anion_name, anion_composition, anion_charge in ANIONS:
        for anion_count in range(1, 7):
            rest = _subtract(composition, anion_composition, anion_count)
            if rest is None or not rest:
                continue
            cation = _rest_cation(rest, anion_charge, anion_count, elements)
            if cation is None:
                continue
            # Ưu tiên gốc chứa ít H nhất (axit tách hết H) rồi gốc giải thích nhiều nguyên tử hơn.
            key = (anion_composition.get("H", 0), -anion_count * sum(anion_composition.values()))
            if best_key is None or key < best_key:
                best_key = key
                best = (
                    cation,
                    Ion(anion_name, anion_charge, anion_count, "anion"),
                )
    return best


def _rest_cation(rest: dict[str, int], anion_charge: int, anion_count: int, elements: dict[str, dict]) -> Ion | None:
    total_negative = -anion_charge * anion_count
    if set(rest) <= {"H"} and rest.get("H"):
        count = rest["H"]
        if total_negative % count != 0:
            return None
        charge = total_negative // count
        if charge != 1:
            return None
        return Ion("H", 1, count, "cation")
    if set(rest) <= {"N", "H"} and rest.get("N") and rest.get("H") == 4 * rest["N"]:
        count = rest["N"]
        if total_negative % count != 0:
            return None
        charge = total_negative // count
        if charge != 1:
            return None
        return Ion("NH4", 1, count, "cation")
    if len(rest) != 1:
        return None
    symbol, count = next(iter(rest.items()))
    if not _is_metal(symbol, elements) or count <= 0 or total_negative % count != 0:
        return None
    charge = total_negative // count
    if charge <= 0 or not _valence_ok(symbol, charge, elements):
        return None
    return Ion(symbol, charge, count, "cation")


def _parse_oxide(formula: str, composition: dict[str, int], compound: dict, elements: dict[str, dict]) -> Species | None:
    if formula == "Fe3O4":
        return Species(
            formula=formula,
            compound=compound,
            composition=composition,
            kind="oxide",
            element="Fe",
            oxide_kind="mixed",
            mixed_valences=(2, 3),
            oxidation={"O": -2},
            metal_valence=None,
            solubility=compound.get("soluble") or "chua_ro",
        )
    if formula == "Co3O4":
        return Species(
            formula=formula,
            compound=compound,
            composition=composition,
            kind="oxide",
            element="Co",
            oxide_kind="mixed",
            mixed_valences=(2, 3),
            oxidation={"O": -2},
            solubility=compound.get("soluble") or "chua_ro",
        )
    if "O" not in composition or len(composition) != 2:
        return None
    other = next(element for element in composition if element != "O")
    oxygen_count = composition["O"]
    other_count = composition[other]
    declared = compound.get("class") or ""
    oxide_kind = None
    if declared == "oxit_axit" or (not _is_metal(other, elements) and declared.startswith("oxit")):
        oxide_kind = "acidic"
    elif declared == "oxit_luong_tinh" or other in AMPHOTERIC_METALS:
        oxide_kind = "amphoteric" if declared != "oxit_axit" else "acidic"
    elif declared == "oxit_trung_tinh":
        oxide_kind = "neutral"
    elif _is_metal(other, elements):
        oxide_kind = "basic"

    charge = None
    peroxide = False
    # Điện tích dương của kim loại cân bằng với O(-2): (2 * số O) chia số nguyên tử kim loại.
    if _is_metal(other, elements) and (2 * oxygen_count) % other_count == 0:
        candidate = (2 * oxygen_count) // other_count
        if candidate > 0 and _valence_ok(other, candidate, elements):
            charge = candidate
    if charge is None and _is_metal(other, elements) and oxygen_count % other_count == 0:
        candidate = oxygen_count // other_count
        if candidate == 1 and _valence_ok(other, 1, elements):
            charge = 1
            peroxide = True
    if charge is None and oxygen_count == 2 * other_count and _is_metal(other, elements) and _valence_ok(other, 1, elements):
        # KO2: kali +1, nhóm O2 có điện tích -1 (SGK, superoxit).
        charge = 1
        peroxide = True
    if oxide_kind is None and charge is None and not declared.startswith("oxit"):
        return None
    oxidation = {"O": -1 if peroxide else -2}
    if charge is not None:
        oxidation[other] = charge
    elif oxygen_count:
        # Phi kim: O = -2, nguyên tố còn lại cân bằng về 0.
        oxidation[other] = (2 * oxygen_count) // other_count
    cation = Ion(other, charge, other_count, "cation") if charge else None
    species = Species(
        formula=formula,
        compound=compound,
        composition=composition,
        kind="oxide",
        element=other,
        cation=cation,
        anion=Ion("O", -1 if peroxide else -2, oxygen_count, "anion"),
        oxidation=oxidation,
        metal_valence=charge,
        oxide_kind="peroxide" if peroxide else (oxide_kind or "basic"),
        solubility=compound.get("soluble") or "chua_ro",
    )
    return species


def parse_species(compound: dict, elements: dict[str, dict]) -> Species:
    formula = compound["formula"]
    composition = dict(compound.get("composition") or {})
    declared = compound.get("class") or ""
    if declared.startswith("don_chat") or (
        len(composition) == 1 and formula.rstrip("0123456789") in elements and formula[:1].isupper()
    ):
        element = next(iter(composition))
        kind = "metal" if declared == "don_chat_kim_loai" or _is_metal(element, elements) else "nonmetal"
        if declared == "don_chat_khi_hiem":
            kind = "noble"
        return Species(
            formula=formula,
            compound=compound,
            composition=composition,
            kind=kind,
            element=element,
            oxidation={element: 0},
            solubility=compound.get("soluble") or "chua_ro",
        )
    if formula == "H2O":
        return Species(
            formula=formula,
            compound=compound,
            composition=composition,
            kind="water",
            oxidation={"H": 1, "O": -2},
            solubility=compound.get("soluble") or "chua_ro",
        )
    if formula == "H2O2":
        return Species(
            formula=formula,
            compound=compound,
            composition=composition,
            kind="peroxide",
            oxidation={"H": 1, "O": -1},
            solubility=compound.get("soluble") or "chua_ro",
        )

    fitted = _fit_ions(composition, elements)
    if fitted and not (declared.startswith("oxit") and fitted[1].formula == "OH"):
        cation, anion = fitted
        oxidation = {}
        oxidation.update(_central_oxidation(anion.formula, anion.charge))
        if cation.formula == "H":
            oxidation["H"] = 1
            kind = "acid"
        elif cation.formula == "NH4":
            oxidation.update({"N": -3, "H": 1})
            kind = "salt"
        elif anion.formula == "OH":
            oxidation = {cation.formula: cation.charge, "O": -2, "H": 1}
            kind = "base"
        else:
            oxidation[cation.formula] = cation.charge
            kind = "salt"
        oxide_instead = None
        if declared.startswith("oxit") and kind == "salt":
            oxide_instead = _parse_oxide(formula, composition, compound, elements)
        if oxide_instead is not None and oxide_instead.cation is not None and len(composition) == 2:
            if oxide_instead.solubility == "chua_ro" and oxide_instead.cation and oxide_instead.anion:
                inferred = solubility_from_ions(oxide_instead.cation.formula, "O")
                if inferred and oxide_instead.oxide_kind == "basic":
                    oxide_instead.solubility, oxide_instead.soluble_basis = inferred
            return oxide_instead
        else:
            basis = ""
            solubility = compound.get("soluble") or "chua_ro"
            if solubility == "chua_ro":
                inferred = solubility_from_ions(cation.formula, anion.formula)
                if inferred:
                    solubility, basis = inferred
            return Species(
                formula=formula,
                compound=compound,
                composition=composition,
                kind=kind,
                element=cation.formula if cation.formula not in {"H", "NH4"} else None,
                cation=cation,
                anion=anion,
                oxidation=oxidation,
                metal_valence=None if cation.formula in {"H", "NH4"} else cation.charge,
                solubility=solubility,
                soluble_basis=basis,
            )

    oxide = _parse_oxide(formula, composition, compound, elements)
    if oxide is not None:
        if oxide.solubility == "chua_ro" and oxide.cation and oxide.anion:
            inferred = solubility_from_ions(oxide.cation.formula, "O")
            if inferred and oxide.oxide_kind == "basic":
                oxide.solubility, oxide.soluble_basis = inferred
        return oxide

    return Species(
        formula=formula,
        compound=compound,
        composition=composition,
        kind="other",
        solubility=compound.get("soluble") or "chua_ro",
    )


def derived_compound_fields(compound: dict, elements: dict[str, dict]) -> dict:
    """Các trường bổ sung ghi vào hồ sơ chất. Tính tan đã nhập được giữ nguyên."""
    species = parse_species(compound, elements)
    ions = []
    if species.cation:
        ions.append(
            {
                "formula": species.cation.formula,
                "charge": species.cation.charge,
                "count": species.cation.count,
                "role": "cation",
            }
        )
    if species.anion and species.kind != "oxide":
        ions.append(
            {
                "formula": species.anion.formula,
                "charge": species.anion.charge,
                "count": species.anion.count,
                "role": "anion",
            }
        )
    elif species.kind == "oxide" and species.anion:
        ions.append(
            {
                "formula": "O",
                "charge": species.anion.charge,
                "count": species.anion.count,
                "role": "anion",
            }
        )
    stored_soluble = compound.get("soluble") or "chua_ro"
    soluble = stored_soluble
    soluble_basis = ""
    if stored_soluble == "chua_ro" and species.solubility != "chua_ro":
        soluble = species.solubility
        soluble_basis = species.soluble_basis
    radical = None
    if species.kind in {"salt", "acid", "base"} and species.anion:
        radical = species.anion.formula
    return {
        "ions": ions,
        "acid_radical": radical,
        "metal_valence": species.metal_valence,
        "oxidation": species.oxidation,
        "soluble": soluble,
        "soluble_basis": soluble_basis,
    }


class Catalog:
    """Chỉ mục chất để luật dựng muối, oxit và so sánh hoạt động hóa học."""

    def __init__(self, compounds: list[dict], elements: list[dict], activity_series: list[str]):
        self.elements = {item["symbol"]: item for item in elements}
        self.compounds = {item["formula"]: item for item in compounds}
        self.activity = {symbol: index + 1 for index, symbol in enumerate(activity_series)}
        self.species: dict[str, Species] = {}
        self.by_ions: dict[tuple[str, int, str], list[str]] = {}
        self.oxides: dict[tuple[str, int], list[str]] = {}
        for compound in compounds:
            species = parse_species(compound, self.elements)
            # Tính tan đã được người lập dữ liệu ghi thì giữ, không suy đè.
            if compound.get("soluble") and compound.get("soluble") != "chua_ro":
                species.solubility = compound["soluble"]
                species.soluble_basis = ""
            self.species[compound["formula"]] = species
            if species.cation and species.anion and species.kind in {"salt", "acid", "base"}:
                key = (species.cation.formula, species.cation.charge, species.anion.formula)
                self.by_ions.setdefault(key, []).append(compound["formula"])
            if species.kind == "oxide" and species.cation and species.oxide_kind != "peroxide":
                key = (species.cation.formula, species.cation.charge)
                self.oxides.setdefault(key, []).append(compound["formula"])

    def activity_of(self, symbol: str | None) -> int | None:
        if not symbol:
            return None
        if symbol in self.activity:
            return self.activity[symbol]
        element = self.elements.get(symbol) or {}
        activity = element.get("activity")
        return int(activity) if isinstance(activity, int) else None

    def get(self, formula: str) -> Species | None:
        return self.species.get(formula)

    def salts(self, cation: str, charge: int, anion: str) -> list[str]:
        return list(self.by_ions.get((cation, charge, anion), []))

    def salt(self, cation: str, charge: int, anion: str) -> str | None:
        found = self.salts(cation, charge, anion)
        if not found:
            return None
        def rank(formula: str) -> tuple:
            kind = self.species[formula].kind
            return (0 if kind == "salt" else 1, len(formula), formula)
        return sorted(found, key=rank)[0]

    def oxide(self, metal: str, charge: int) -> str | None:
        found = list(self.oxides.get((metal, charge), []))
        if not found:
            return None
        def rank(formula: str) -> tuple:
            kind = self.species[formula].oxide_kind
            order = {"basic": 0, "amphoteric": 1, "mixed": 2, "acidic": 3, "neutral": 4}
            return (order.get(kind or "", 5), len(self.species[formula].composition), formula)
        return sorted(found, key=rank)[0]

    def is_gas(self, formula: str) -> bool:
        if formula in GAS_FORMULAS:
            return True
        species = self.species.get(formula)
        if species is None:
            return False
        return species.compound.get("state") == "khi"

    def is_precipitate(self, formula: str) -> bool:
        if self.is_gas(formula):
            return False
        species = self.species.get(formula)
        if species is None:
            return False
        return species.solubility in {"khong_tan", "it_tan"}

    def is_weak(self, formula: str) -> bool:
        return formula in WEAK_ELECTROLYTES or formula == "H2O"

    def acid_rank(self, formula: str) -> int:
        if formula in STRONG_ACIDS:
            return 2
        species = self.species.get(formula)
        if species and species.kind == "acid":
            return 0
        return 1
