"""Điền kết quả suy diễn vào template lời giải tiếng Việt."""

from __future__ import annotations

from app.core.formula import composition_text
from app.core.numbers import format_number


class TemplateError(KeyError):
    pass


def render(template: str, values: dict) -> str:
    try:
        return template.format(**values)
    except KeyError as error:
        missing = error.args[0]
        raise TemplateError(f"Template thiếu dữ liệu '{missing}'.") from error


def _line(templates: dict[str, str], key: str, **values) -> str:
    template = templates.get(key)
    if not template:
        raise TemplateError(f"Không có template '{key}'.")
    return render(template, values)


def render_balance(result: dict, templates: dict[str, str]) -> list[str]:
    species = result["reactants"] + result["products"]
    compositions = result["compositions"]
    symbols = result["symbols"]
    steps: list[str] = []

    steps.append(_line(templates, "balance.intro", equation=result["unbalanced"]))

    composition_lines = [_line(templates, "balance.composition_header")]
    for formula, composition in zip(species, compositions):
        composition_lines.append(
            _line(templates, "balance.composition_item", formula=formula, atoms=composition_text(composition))
        )
    steps.append("\n".join(composition_lines))

    reactant_count = len(result["reactants"])
    left = " + ".join(f"{symbols[index]} {species[index]}" for index in range(reactant_count))
    right = " + ".join(f"{symbols[index]} {species[index]}" for index in range(reactant_count, len(species)))
    steps.append(_line(templates, "balance.unknowns", equation=f"{left} → {right}"))

    equation_lines = [_line(templates, "balance.system_header")]
    for item in result["equations"]:
        equation_lines.append(_line(templates, "balance.system_item", element=item["element"], equation=item["text"]))
    steps.append("\n".join(equation_lines))

    solve_lines = [_line(templates, "balance.solve_header")]
    for event in result["trace"]:
        action = event["action"]
        if action == "choose_free":
            solve_lines.append(
                _line(
                    templates,
                    "balance.choose_free",
                    formula=event["formula"],
                    value=event["value"],
                    reason=event["reason"],
                )
            )
        elif action == "conserve":
            solve_lines.append(
                _line(
                    templates,
                    "balance.conserve",
                    element=event["element"],
                    formula=event["formula"],
                    value=event["value"],
                    equation=event["equation"],
                )
            )
        elif action == "scale":
            solve_lines.append(
                _line(templates, "balance.scale", factor=event["factor"], coefficients=event["coefficients_text"])
            )
        elif action == "gcd":
            key = "balance.gcd_keep" if event["gcd"] == 1 else "balance.gcd_reduce"
            solve_lines.append(_line(templates, key, gcd=event["gcd"]))
        elif action == "assign":
            solve_lines.append(
                _line(templates, "balance.assign", formula=event["formula"], value=event["value"])
            )
        elif action == "normalized":
            solve_lines.append(_line(templates, "balance.normalized", coefficients=event["coefficients_text"]))
    steps.append("\n".join(solve_lines))

    check_lines = [_line(templates, "balance.check_header")]
    for item in result["checks"]:
        check_lines.append(
            _line(
                templates,
                "balance.check_item",
                element=item["element"],
                left=item["left"],
                right=item["right"],
            )
        )
    steps.append("\n".join(check_lines))
    steps.append(_line(templates, "balance.result", equation=result["balanced"]))
    return _number_steps(steps)


def render_chain(result: dict, templates: dict[str, str]) -> list[str]:
    if result.get("same"):
        return [_line(templates, "chain.already", formula=result["start"])]
    if not result.get("found"):
        return [
            _line(
                templates,
                "chain.not_found",
                start=result["start"],
                target=result["target"],
                max_steps=result["max_steps"],
            )
        ]

    steps = [
        _line(templates, "chain.intro", start=result["start"], target=result["target"])
    ]
    for item in result["reactions"]:
        block = [
            _line(
                templates,
                "chain.step",
                index=item["index"],
                source=item["from"],
                product=item["to"],
                type_label=item["type_label"],
                condition_label=item["condition_label"],
            ),
            _line(templates, "chain.equation", equation=item["equation"]),
        ]
        if item["auxiliaries"]:
            block.append(_line(templates, "chain.aux", auxiliaries=", ".join(item["auxiliaries"])))
        else:
            block.append(_line(templates, "chain.no_aux"))
        if item.get("rule_id"):
            block.append(_line(templates, "chain.rule", rule_id=item["rule_id"], rule_text=item["rule_text"]))
        else:
            block.append(_line(templates, "chain.no_rule"))
        if item["byproducts"]:
            block.append(_line(templates, "chain.byproducts", byproducts=", ".join(item["byproducts"])))
        steps.append("\n".join(block))

    listing = "\n".join(f"({item['index']}) {item['equation']}" for item in result["reactions"])
    steps.append(
        _line(
            templates,
            "chain.summary",
            count=len(result["reactions"]),
            start=result["start"],
            target=result["target"],
            listing=listing,
        )
    )
    return _number_steps(steps)


def render_quantity(balance_steps: list[str], quantity: dict, templates: dict[str, str]) -> list[str]:
    """Ghép phần cân bằng đã đánh số với các bước tính đại lượng."""
    steps = list(balance_steps)
    start_index = len(steps) + 1
    known = quantity["known_formula"]
    find = quantity["find_formula"]
    kind = quantity["known_kind"]

    if kind == "mass":
        mole_line = _line(
            templates,
            "quantity.mole_from_mass",
            formula=known,
            mass=format_number(quantity["known_value"]),
            molar_mass=format_number(quantity["molar_mass_known"]),
            moles=format_number(quantity["moles_known"]),
        )
    elif kind == "volume":
        mole_line = _line(
            templates,
            "quantity.mole_from_volume",
            formula=known,
            volume=format_number(quantity["known_value"]),
            molar_volume=format_number(quantity["molar_volume"]),
            moles=format_number(quantity["moles_known"]),
        )
    else:
        mole_line = _line(
            templates,
            "quantity.mole_from_mole",
            formula=known,
            moles=format_number(quantity["moles_known"]),
        )
    steps.append(f"Bước {start_index}: {mole_line}")

    if quantity["coeff_known"] == quantity["coeff_find"]:
        ratio_line = _line(
            templates,
            "quantity.ratio_equal",
            known=known,
            find=find,
            moles=format_number(quantity["moles_find"]),
        )
    else:
        ratio_line = _line(
            templates,
            "quantity.ratio",
            known=known,
            find=find,
            coeff_known=quantity["coeff_known"],
            coeff_find=quantity["coeff_find"],
            moles_known=format_number(quantity["moles_known"]),
            moles_find=format_number(quantity["moles_find"]),
            ratio=_ratio_text(quantity["coeff_find"], quantity["coeff_known"]),
        )
    steps.append(f"Bước {start_index + 1}: {ratio_line}")

    find_kind = quantity["find_kind"]
    if find_kind == "mass":
        value_line = _line(
            templates,
            "quantity.mass",
            formula=find,
            moles=format_number(quantity["moles_find"]),
            molar_mass=format_number(quantity["molar_mass_find"]),
            value=format_number(quantity["value"]),
        )
    elif find_kind == "volume":
        value_line = _line(
            templates,
            "quantity.volume",
            formula=find,
            moles=format_number(quantity["moles_find"]),
            molar_volume=format_number(quantity["molar_volume"]),
            value=format_number(quantity["value"]),
        )
    else:
        value_line = _line(
            templates,
            "quantity.mole",
            formula=find,
            moles=format_number(quantity["value"]),
        )
    steps.append(f"Bước {start_index + 2}: {value_line}")
    steps.append(
        _line(
            templates,
            "quantity.answer",
            formula=find,
            value=format_number(quantity["value"]),
            unit=quantity["unit"],
        )
    )
    return steps


def _ratio_text(coeff_find: int, coeff_known: int) -> str:
    if coeff_find == coeff_known:
        return "1"
    return f"{coeff_find}/{coeff_known}"


def _number_steps(steps: list[str]) -> list[str]:
    numbered = []
    for index, step in enumerate(steps, start=1):
        lines = step.split("\n")
        lines[0] = f"Bước {index}: {lines[0]}"
        numbered.append("\n".join(lines))
    return numbered


def join_explanation(steps: list[str]) -> str:
    return "\n".join(steps)
