"""Cân bằng phương trình bằng bảo toàn nguyên tố và sinh vết giải để điền template."""

from __future__ import annotations

from fractions import Fraction
from math import gcd
from functools import reduce

from app.core.formula import FormulaError, composition_text, format_equation, parse_formula
from app.core.numbers import format_fraction_value, format_number


class BalanceError(ValueError):
    pass


def _rref(matrix: list[list[Fraction]]) -> tuple[list[list[Fraction]], list[int]]:
    rows = [row[:] for row in matrix]
    if not rows:
        return rows, []
    row_count = len(rows)
    col_count = len(rows[0])
    pivot_cols: list[int] = []
    row = 0
    for col in range(col_count):
        pivot = None
        for candidate in range(row, row_count):
            if rows[candidate][col] != 0:
                pivot = candidate
                break
        if pivot is None:
            continue
        rows[row], rows[pivot] = rows[pivot], rows[row]
        factor = rows[row][col]
        rows[row] = [value / factor for value in rows[row]]
        for other in range(row_count):
            if other == row or rows[other][col] == 0:
                continue
            multiplier = rows[other][col]
            rows[other] = [value - multiplier * rows[row][index] for index, value in enumerate(rows[other])]
        pivot_cols.append(col)
        row += 1
        if row == row_count:
            break
    return rows, pivot_cols


def _positive_integer_solution(matrix: list[list[Fraction]]) -> list[int]:
    reduced, pivot_cols = _rref(matrix)
    col_count = len(matrix[0])
    free_cols = [col for col in range(col_count) if col not in pivot_cols]
    if not free_cols:
        raise BalanceError("Phương trình chỉ có nghiệm tầm thường, không cân bằng được.")

    def solution_for(assignment: dict[int, Fraction]) -> list[Fraction] | None:
        values = [Fraction(0) for _ in range(col_count)]
        for col, value in assignment.items():
            values[col] = value
        for row_index, pivot_col in enumerate(pivot_cols):
            if row_index >= len(reduced):
                break
            total = Fraction(0)
            for col in range(col_count):
                if col == pivot_col:
                    continue
                total += reduced[row_index][col] * values[col]
            values[pivot_col] = -total
        if any(value <= 0 for value in values):
            return None
        return values

    # Một ẩn tự do: đặt bằng 1. Nhiều ẩn tự do: thử các giá trị nguyên nhỏ.
    if len(free_cols) == 1:
        found = solution_for({free_cols[0]: Fraction(1)})
        if found is None:
            raise BalanceError("Không tìm được bộ hệ số nguyên dương.")
        candidates = [found]
    else:
        candidates = []
        upper = 4
        ranges = []

        def walk(position: int, current: dict[int, Fraction]) -> None:
            if position == len(free_cols):
                found = solution_for(current)
                if found is not None:
                    candidates.append(found)
                return
            for number in range(1, upper + 1):
                current[free_cols[position]] = Fraction(number)
                walk(position + 1, current)
                if len(candidates) > 12:
                    return

        walk(0, {})
        if not candidates:
            raise BalanceError("Không tìm được bộ hệ số nguyên dương.")

    best_score = None
    best: list[int] | None = None
    for candidate in candidates:
        denominators = [value.denominator for value in candidate]
        factor = reduce(lambda a, b: a * b // gcd(a, b), denominators, 1)
        integers = [int(value * factor) for value in candidate]
        divisor = reduce(gcd, integers)
        integers = [value // divisor for value in integers]
        score = (max(integers), sum(integers))
        if best_score is None or score < best_score:
            best_score = score
            best = integers
    assert best is not None
    return best


def balance_formulas(reactants: list[str], products: list[str]) -> dict:
    if not reactants or not products:
        raise BalanceError("Cần có chất tham gia và sản phẩm.")
    try:
        compositions = [parse_formula(formula) for formula in reactants + products]
    except FormulaError as error:
        raise BalanceError(str(error)) from error

    elements: list[str] = []
    for composition in compositions:
        for element in composition:
            if element not in elements:
                elements.append(element)

    matrix: list[list[Fraction]] = []
    for element in elements:
        row = []
        for index, composition in enumerate(compositions):
            count = composition.get(element, 0)
            if index >= len(reactants):
                count = -count
            row.append(Fraction(count))
        matrix.append(row)

    coefficients = _positive_integer_solution(matrix)
    _assert_conserved(compositions, coefficients, len(reactants), elements)
    trace = _build_trace(reactants, products, compositions, elements, coefficients)
    symbols = _coefficient_symbols(len(reactants) + len(products))
    return {
        "reactants": reactants,
        "products": products,
        "coefficients": coefficients,
        "compositions": compositions,
        "elements": elements,
        "symbols": symbols,
        "unbalanced": format_equation(reactants, products, [1] * (len(reactants) + len(products))),
        "balanced": format_equation(reactants, products, coefficients),
        "trace": trace,
        "checks": _checks(compositions, coefficients, len(reactants), elements),
        "equations": _equation_lines(reactants, products, compositions, elements, symbols),
        "gcd": reduce(gcd, coefficients),
    }


def _assert_conserved(compositions, coefficients, reactant_count, elements) -> None:
    for element in elements:
        left = right = 0
        for index, composition in enumerate(compositions):
            amount = composition.get(element, 0) * coefficients[index]
            if index < reactant_count:
                left += amount
            else:
                right += amount
        if left != right:
            raise BalanceError(f"Không bảo toàn được nguyên tố {element}.")


def _checks(compositions, coefficients, reactant_count, elements) -> list[dict]:
    checks = []
    for element in elements:
        left = right = 0
        for index, composition in enumerate(compositions):
            amount = composition.get(element, 0) * coefficients[index]
            if index < reactant_count:
                left += amount
            else:
                right += amount
        checks.append({"element": element, "left": left, "right": right})
    return checks


def _coefficient_symbols(count: int) -> list[str]:
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    return [alphabet[index] if index < len(alphabet) else f"x{index + 1}" for index in range(count)]


def _equation_lines(reactants, products, compositions, elements, symbols) -> list[dict]:
    reactant_count = len(reactants)
    lines = []
    for element in elements:
        left_terms = []
        right_terms = []
        for index, composition in enumerate(compositions):
            count = composition.get(element, 0)
            if count == 0:
                continue
            symbol = symbols[index]
            term = symbol if count == 1 else f"{count}{symbol}"
            if index < reactant_count:
                left_terms.append(term)
            else:
                right_terms.append(term)
        lines.append(
            {
                "element": element,
                "text": f"{' + '.join(left_terms) if left_terms else '0'} = {' + '.join(right_terms) if right_terms else '0'}",
            }
        )
    return lines


def _build_trace(reactants, products, compositions, elements, coefficients) -> list[dict]:
    """Mô phỏng cách giải lần lượt để diễn giải, rồi đối chiếu với nghiệm đã rút gọn."""
    species = reactants + products
    reactant_count = len(reactants)
    unknown = set(range(len(species)))
    known: dict[int, Fraction] = {}
    trace: list[dict] = []

    def equation_snapshot(element: str, solving_index: int) -> str:
        left = []
        right = []
        for index, composition in enumerate(compositions):
            count = composition.get(element, 0)
            if count == 0:
                continue
            if index == solving_index:
                term = species[index] if count == 1 else f"{count}×{species[index]}"
            else:
                amount = count * known[index]
                term = format_number(amount) if amount.denominator == 1 else format_fraction_value(amount)
            if index < reactant_count:
                left.append(term)
            else:
                right.append(term)
        return f"{' + '.join(left) if left else '0'} = {' + '.join(right) if right else '0'}"

    guard = 0
    while unknown and guard < 30:
        guard += 1
        progressed = False
        for element in elements:
            terms = [(index, compositions[index][element]) for index in range(len(species)) if compositions[index].get(element)]
            pending = [(index, count) for index, count in terms if index not in known]
            if len(pending) != 1 or len(terms) == len(pending):
                continue
            index, count = pending[0]
            known_sum = Fraction(0)
            for other, other_count in terms:
                if other not in known:
                    continue
                sign = 1 if other < reactant_count else -1
                known_sum += sign * other_count * known[other]
            sign = 1 if index < reactant_count else -1
            value = -known_sum / (sign * count)
            equation = equation_snapshot(element, index)
            known[index] = value
            unknown.remove(index)
            trace.append(
                {
                    "action": "conserve",
                    "element": element,
                    "formula": species[index],
                    "value": format_fraction_value(value),
                    "equation": equation,
                }
            )
            progressed = True
            break
        if progressed:
            continue
        if not unknown:
            break
        chosen = max(unknown, key=lambda index: (sum(compositions[index].values()), index))
        known[chosen] = Fraction(1)
        unknown.remove(chosen)
        trace.append(
            {
                "action": "choose_free",
                "formula": species[chosen],
                "value": "1",
                "reason": "đây là chất còn lại nhiều nguyên tử nhất, dùng làm mốc",
            }
        )

    if len(known) != len(species):
        for index, coefficient in enumerate(coefficients):
            trace.append(
                {
                    "action": "assign",
                    "formula": species[index],
                    "value": str(coefficient),
                }
            )
        return trace

    denominators = [value.denominator for value in known.values()]
    factor = reduce(lambda a, b: a * b // gcd(a, b), denominators, 1)
    integers = {index: int(value * factor) for index, value in known.items()}
    divisor = reduce(gcd, integers.values())
    reduced = {index: value // divisor for index, value in integers.items()}
    solved = [reduced[index] for index in range(len(species))]

    if factor != 1:
        trace.append(
            {
                "action": "scale",
                "factor": factor,
                "coefficients_text": ", ".join(
                    f"{species[index]}: {format_fraction_value(known[index])} → {integers[index]}"
                    for index in range(len(species))
                ),
            }
        )
    trace.append({"action": "gcd", "gcd": divisor, "final": solved})
    if solved != coefficients:
        # Diễn giải tuần tự lệch nghiệm tối giản thì dùng nghiệm đại số đã kiểm chứng.
        trace.append(
            {
                "action": "normalized",
                "coefficients_text": ", ".join(
                    f"{formula}: {coefficient}" for formula, coefficient in zip(species, coefficients)
                ),
            }
        )
    return trace
