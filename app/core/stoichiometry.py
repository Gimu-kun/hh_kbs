"""Tính đại lượng theo phương trình đã cân bằng."""

from __future__ import annotations

from fractions import Fraction

from app.core.constants import GAS_FORMULAS, MOLAR_VOLUME_STP
from app.core.numbers import to_fraction


class QuantityError(ValueError):
    pass


def molar_mass(formula: str, composition: dict[str, int], elements: dict[str, dict]) -> Fraction:
    total = Fraction(0)
    for symbol, count in composition.items():
        element = elements.get(symbol)
        if element is None:
            raise QuantityError(f"Chưa có nguyên tố {symbol} trong cơ sở tri thức nên không tính được khối lượng mol của {formula}.")
        total += to_fraction(element["mass"]) * count
    return total


def is_gas(formula: str, compound: dict | None) -> bool:
    if formula in GAS_FORMULAS:
        return True
    return bool(compound and compound.get("state") == "khi")


def solve_quantity(
    reactants: list[str],
    products: list[str],
    coefficients: list[int],
    known_formula: str,
    known_kind: str,
    known_value: Fraction,
    find_formula: str,
    find_kind: str,
    compositions: dict[str, dict[str, int]],
    elements: dict[str, dict],
    compounds: dict[str, dict],
    molar_volume: Fraction,
) -> dict:
    species = reactants + products
    if known_formula not in species:
        raise QuantityError(f"Chất đã biết {known_formula} không có trong phương trình.")
    if find_formula not in species:
        raise QuantityError(f"Chất cần tìm {find_formula} không có trong phương trình.")

    coeff_known = coefficients[species.index(known_formula)]
    coeff_find = coefficients[species.index(find_formula)]
    mass_known = molar_mass(known_formula, compositions[known_formula], elements)
    mass_find = molar_mass(find_formula, compositions[find_formula], elements)

    if known_kind == "mass":
        if known_value <= 0:
            raise QuantityError("Khối lượng đã biết phải lớn hơn 0.")
        moles_known = known_value / mass_known
    elif known_kind == "volume":
        if not is_gas(known_formula, compounds.get(known_formula)):
            raise QuantityError(f"{known_formula} không phải chất khí trong điều kiện tiêu chuẩn, không đổi thể tích ra số mol bằng 22,4 lít/mol.")
        if known_value <= 0:
            raise QuantityError("Thể tích đã biết phải lớn hơn 0.")
        moles_known = known_value / molar_volume
    elif known_kind == "mole":
        if known_value <= 0:
            raise QuantityError("Số mol đã biết phải lớn hơn 0.")
        moles_known = known_value
    else:
        raise QuantityError("Đại lượng đã biết chỉ nhận mass, volume hoặc mole.")

    moles_find = moles_known * Fraction(coeff_find, coeff_known)

    if find_kind == "mass":
        value = moles_find * mass_find
        unit = "g"
    elif find_kind == "volume":
        if not is_gas(find_formula, compounds.get(find_formula)):
            raise QuantityError(f"{find_formula} không phải chất khí, không tính thể tích ở đktc.")
        value = moles_find * molar_volume
        unit = "lít"
    elif find_kind == "mole":
        value = moles_find
        unit = "mol"
    else:
        raise QuantityError("Đại lượng cần tìm chỉ nhận mass, volume hoặc mole.")

    return {
        "coeff_known": coeff_known,
        "coeff_find": coeff_find,
        "molar_mass_known": mass_known,
        "molar_mass_find": mass_find,
        "moles_known": moles_known,
        "moles_find": moles_find,
        "value": value,
        "unit": unit,
        "molar_volume": molar_volume,
    }
