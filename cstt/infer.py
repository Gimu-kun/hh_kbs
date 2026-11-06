"""Máy suy diễn cho ba dạng bài: cân bằng, chuỗi phản ứng, tính lượng chất."""

from __future__ import annotations

import re
from collections import deque
from fractions import Fraction

from cstt.chem import ChemError, balance, format_equation, molar_mass
from cstt.kb import KnowledgeBase, load_kb
from cstt.present import (
    don_vi_chu,
    giai_thich_tu_nhien,
    liet_ke,
    reset_templates,
    so_sgk,
    ten_dai_luong,
    trinh_bay,
    viet_thuong,
)
from cstt.reactions import Reaction, ensure_reactions

_KB: KnowledgeBase | None = None


def get_kb() -> KnowledgeBase:
    global _KB
    if _KB is None:
        _KB = load_kb()
    return _KB


def reload_kb() -> KnowledgeBase:
    global _KB
    _KB = load_kb()
    reset_templates()
    return _KB


def _step(steps: list[dict], direction: str, rule: str, content: str, mau: str | None = None, tham_so: dict | None = None) -> None:
    step = {"buoc": len(steps) + 1, "chieu": direction, "luat": rule, "noi_dung": content}
    if mau:
        step["mau"] = mau
        step["tham_so"] = tham_so or {}
    steps.append(step)


def _pack(result: dict, truong_hop: str, tham_so: dict | None = None) -> dict:
    result["_truong_hop"] = truong_hop
    result["_tham_so"] = tham_so or {}
    return result


def _cong_bo(problem: dict, result: dict) -> dict:
    result["trinh_bay"] = trinh_bay(problem, result)
    result.pop("_truong_hop", None)
    result.pop("_tham_so", None)
    for step in result.get("vet") or []:
        step.pop("mau", None)
        step.pop("tham_so", None)
    return result


def _show_number(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    as_float = float(value)
    text = f"{as_float:.6f}".rstrip("0").rstrip(".")
    return text


def _parse_equation(text: str) -> tuple[list[str], list[str]]:
    normalized = text.replace("→", "->").replace("=", "->")
    if "->" not in normalized:
        raise ChemError("Phương trình cần có dấu -> hoặc →.")
    left, right = normalized.split("->", 1)
    reactants = [item.strip() for item in left.split("+") if item.strip()]
    products = [item.strip() for item in right.split("+") if item.strip()]
    reactants = [re.sub(r"^\d+", "", item) for item in reactants]
    products = [re.sub(r"^\d+", "", item) for item in products]
    if not reactants or not products:
        raise ChemError("Phương trình thiếu chất tham gia hoặc sản phẩm.")
    return reactants, products


def _require_known(kb: KnowledgeBase, formulas: list[str], steps: list[dict]) -> None:
    for formula in formulas:
        if formula not in kb.compounds:
            raise ChemError(f"Chất {formula} không có trong phạm vi THCS đã nạp.")
        compound = kb.compounds[formula]
        _step(
            steps,
            "tien",
            "R1",
            f"Kiểm tra {formula}: R1 xếp vào lớp {compound.class_label}. "
            f"Thành phần {[item['element'] + str(item['quantity']) if item['quantity'] != 1 else item['element'] for item in compound.composition]}.",
            "R1_KIEM_TRA",
            {"cong_thuc": formula, "lop": viet_thuong(compound.class_label)},
        )


def solve_balance(equation: str, kb: KnowledgeBase | None = None) -> dict:
    kb = kb or get_kb()
    steps: list[dict] = []
    reactants, products = _parse_equation(equation)
    _require_known(kb, reactants + products, steps)
    compositions = {formula: kb.compounds[formula].comp for formula in reactants + products}
    coefficients = balance(reactants, products, compositions)
    if coefficients is None:
        return _pack(
            {
                "co_loi_giai": False,
                "thong_bao": "Không có bộ hệ số nguyên dương nào bảo toàn mọi nguyên tố.",
                "vet": steps,
            },
            "loai_1_khong_bao_toan",
        )
    left = [(formula, coefficients[index]) for index, formula in enumerate(reactants)]
    right = [(formula, coefficients[index + len(reactants)]) for index, formula in enumerate(products)]
    balanced = format_equation(left, right)
    elements = sorted({symbol for formula in reactants + products for symbol in compositions[formula]})
    for symbol in elements:
        total_left = sum(coeff * compositions[formula].get(symbol, 0) for formula, coeff in left)
        total_right = sum(coeff * compositions[formula].get(symbol, 0) for formula, coeff in right)
        _step(
            steps,
            "tien",
            "BAO_TOAN",
            f"Bảo toàn {symbol}: vế trái {total_left} nguyên tử, vế phải {total_right} nguyên tử.",
            "BAO_TOAN_NGUYEN_TO",
            {
                "ten": viet_thuong(kb.elements[symbol]["name"]),
                "ky_hieu": symbol,
                "trai": str(total_left),
                "phai": str(total_right),
            },
        )
    _step(steps, "tien", "BAO_TOAN", f"Hệ số nguyên dương nhỏ nhất cho {balanced}.")
    return _pack(
        {"co_loi_giai": True, "phuong_trinh": balanced, "he_so": coefficients, "vet": steps},
        "loai_1_thanh_cong",
    )


def _tracked_elements(kb: KnowledgeBase, formula: str) -> frozenset[str]:
    """Nguyên tố phải được chuyển tiếp. H và O chỉ được tính khi chất không có nguyên tố khác."""
    elements = frozenset(kb.compounds[formula].comp)
    core = elements - {"H", "O"}
    return core or elements


def _keeps_lineage(kb: KnowledgeBase, reactant: str, start: str, target: str, reaction: Reaction, product: str) -> bool:
    shared = _tracked_elements(kb, start) & _tracked_elements(kb, target)
    if reactant == start:
        if shared:
            return True
        # Chất đầu không mang nguyên tố đích thì chỉ được vào ở bước tạo ra chính nguyên tố đó.
        # Nước tham gia tạo NaCl rồi điện phân ra Na là cầu nối, không phải bước chuyển hoá.
        target_elements = _tracked_elements(kb, target)
        if not (_tracked_elements(kb, product) & target_elements):
            return False
        others = [formula for formula, _ in reaction.reactants if formula != reactant]
        other_has_target = any(_tracked_elements(kb, other) & target_elements for other in others)
        product_is_element = kb.compounds[product].class_id in {"don_chat_kim_loai", "don_chat_phi_kim"}
        return not other_has_target or product_is_element
    tracked = _tracked_elements(kb, reactant)
    if shared:
        return shared <= tracked
    return bool(tracked & _tracked_elements(kb, target))


def _reagents_are_independent(reaction: Reaction, traced: str, target: str, path: list[Reaction]) -> bool:
    """Thuốc thử không được là chất đích hoặc chất chỉ xuất hiện ở bước sau."""
    produced = {target}
    for step in path:
        produced.update(formula for formula, _ in step.products)
    return all(formula not in produced for formula, _ in reaction.reactants if formula != traced)


def _search_chain(
    kb: KnowledgeBase,
    start: str,
    target: str,
    limit: int,
    allowed: set[str] | None,
) -> list[Reaction] | None:
    reactions = ensure_reactions(kb)
    coming_from: dict[str, list[tuple[str, Reaction]]] = {}
    for reaction in reactions:
        products = {formula for formula, _ in reaction.products}
        reactants = [formula for formula, _ in reaction.reactants]
        for product in products:
            for reactant in reactants:
                if reactant != product:
                    coming_from.setdefault(product, []).append((reactant, reaction))
    queue = deque([(target, [])])
    seen = {target}
    while queue:
        current, path = queue.popleft()
        if current == start and path:
            return path
        if len(path) >= limit:
            continue
        for reactant, reaction in coming_from.get(current, []):
            if reactant in seen or not _keeps_lineage(kb, reactant, start, target, reaction, current):
                continue
            if not _reagents_are_independent(reaction, reactant, target, path):
                continue
            if allowed is not None:
                others = {formula for formula, _ in reaction.reactants if formula != reactant}
                if not others <= allowed | {start}:
                    continue
            seen.add(reactant)
            queue.append((reactant, [reaction] + path))
    return None


def solve_chain(
    start: str,
    target: str,
    kb: KnowledgeBase | None = None,
    mode: str = "tat_ca",
    allowed: list[str] | None = None,
) -> dict:
    kb = kb or get_kb()
    steps: list[dict] = []
    if mode not in {"tat_ca", "cho_truoc"}:
        raise ChemError("che_do phải là tat_ca hoặc cho_truoc.")
    allowed_set: set[str] | None = None
    if mode == "cho_truoc":
        if allowed is None:
            raise ChemError("Chế độ cho_truoc cần danh sách chat_cho_phep.")
        _require_known(kb, allowed, steps)
        allowed_set = set(allowed)
    _require_known(kb, [start, target], steps)
    if start == target:
        _step(steps, "lui", "R2", f"{start} đã là chất cần tìm.")
        for step in steps:
            step.pop("mau", None)
            step.pop("tham_so", None)
        return _pack(
            {"co_loi_giai": True, "che_do": mode, "chuoi": [], "vet": steps},
            "loai_2_da_la_dich",
            {"chat": start},
        )
    limit = kb.r2["max_depth"]
    if mode == "tat_ca":
        rule_text = "Mọi chất trong phạm vi THCS đều được dùng làm thuốc thử."
        mau = "D2_MO_TAT_CA"
        mo_ta = {"chat_dau": start, "chat_dich": target, "do_sau": str(limit)}
    else:
        names = ", ".join(allowed or [])
        rule_text = f"Chỉ được dùng các chất cho trước: {names}. Chất sinh ra ở bước trước được dùng tiếp."
        mau = "D2_MO_CHO_TRUOC"
        mo_ta = {
            "chat_dau": start,
            "chat_dich": target,
            "do_sau": str(limit),
            "thuoc_thu": liet_ke(list(allowed or [])),
        }
    _step(
        steps,
        "lui",
        "R2",
        f"Đặt mục tiêu {target}. Suy diễn lùi từ chất đầu {start}. {rule_text} "
        "Mỗi bước phải chuyển tiếp nguyên tố đặc trưng; sản phẩm phụ như H2O không được làm cầu nối. "
        f"Độ sâu tối đa {limit} phản ứng.",
        mau,
        mo_ta,
    )
    path = _search_chain(kb, start, target, limit, allowed_set)
    if not path:
        scope = "các chất cho trước" if mode == "cho_truoc" else "phạm vi luật"
        return _pack(
            {
                "co_loi_giai": False,
                "che_do": mode,
                "thong_bao": (
                    f"Không tìm thấy chuỗi từ {start} tới {target} trong {scope}, tối đa {limit} bước. "
                    "Các bước phải chuyển tiếp nguyên tố đặc trưng, không nối qua sản phẩm phụ."
                ),
                "vet": steps,
            },
            "loai_2_khong_co_duong",
            {
                "chat_dau": start,
                "chat_dich": target,
                "do_sau": str(limit),
                "pham_vi": "các chất cho trước" if mode == "cho_truoc" else "phạm vi thuốc thử của chương trình",
            },
        )
    sequence = []
    for reaction in path:
        text = reaction.text(kb)
        sequence.append(text)
        _step(
            steps,
            "lui",
            reaction.rule_id,
            f"{reaction.explain} Phương trình: {text}.",
            "D2_BUOC",
            {"giai_thich": giai_thich_tu_nhien(reaction.explain, reaction.rule_name), "phuong_trinh": text},
        )
    return _pack(
        {"co_loi_giai": True, "che_do": mode, "chuoi": sequence, "so_buoc": len(sequence), "vet": steps},
        "loai_2_thanh_cong",
        {"chat_dau": start, "chat_dich": target, "so_buoc": str(len(sequence)), "chuoi": "; ".join(sequence)},
    )


def _vm(kb: KnowledgeBase) -> Fraction:
    for item in kb.formulas["constants"]:
        if item["symbol"] == "Vm":
            return Fraction(str(item["value"]))
    raise ChemError("Thiếu hằng số Vm.")


def _solve_one(facts: dict, key, compute, steps: list[dict], rule: str, content: str) -> bool:
    if key in facts:
        return False
    facts[key] = compute
    _step(steps, "tien", rule, content)
    return True


def _apply_ratio(
    facts: dict[tuple[str, str], Fraction],
    species: list[str],
    coeff: dict[str, int],
    reactant_names: set[str],
    steps: list[dict],
) -> tuple[str | None, bool | None]:
    """Áp dụng n1/hệ số 1 = n2/hệ số 2 theo cả hai chiều.

    Trả về (thông báo lỗi, đã điền số mol mới). Giá trị thứ hai là None khi chưa có số mol nào.
    """
    known_reactants = [formula for formula in species if formula in reactant_names and (formula, "n") in facts]
    known_products = [formula for formula in species if formula not in reactant_names and (formula, "n") in facts]
    if not known_reactants and not known_products:
        return None, None

    def extent_of(formula: str) -> Fraction:
        return facts[(formula, "n")] / coeff[formula]

    limit = None
    limiting: list[str] = []
    if known_reactants:
        limit = min(extent_of(formula) for formula in known_reactants)
        limiting = [formula for formula in known_reactants if extent_of(formula) == limit]
    product_extent = None
    if known_products:
        amounts = {extent_of(formula) for formula in known_products}
        if len(amounts) > 1:
            return "lech", None
        product_extent = amounts.pop()
    if limit is not None and product_extent is not None and product_extent > limit:
        return "vuot", None

    if product_extent is not None and (limit is None or product_extent < limit):
        extent = product_extent
        named = ", ".join(known_products)
        _step(
            steps,
            "tien",
            "F_RATIO",
            f"Mức phản ứng lấy theo sản phẩm đã biết ({named}) = {_show_number(extent)} mol.",
            "F_RATIO_SAN_PHAM",
            {"san_pham": liet_ke(known_products), "muc": so_sgk(extent)},
        )
    else:
        extent = limit
        if len(known_reactants) > 1:
            _step(
                steps,
                "tien",
                "F_RATIO",
                "Có số mol của nhiều chất tham gia. Mức phản ứng lấy theo chất hết trước: "
                + ", ".join(limiting)
                + f". Mức phản ứng = {_show_number(extent)} mol.",
                "F_RATIO_HET_TRUOC",
                {"chat_het": liet_ke(limiting), "muc": so_sgk(extent)},
            )
    added = False
    for formula in species:
        predicted = extent * coeff[formula]
        mole_key = (formula, "n")
        if mole_key not in facts:
            facts[mole_key] = predicted
            _step(
                steps,
                "tien",
                "F_RATIO",
                f"n({formula}) = mức phản ứng × hệ số {coeff[formula]} = {_show_number(predicted)} mol.",
                "F_RATIO_N",
                {"chat": formula, "he_so": str(coeff[formula]), "n": so_sgk(predicted)},
            )
            added = True
        elif formula in reactant_names and facts[mole_key] > predicted:
            _step(
                steps,
                "tien",
                "F_RATIO",
                f"{formula} dư: đề cho {_show_number(facts[mole_key])} mol, phản ứng dùng {_show_number(predicted)} mol.",
                "F_RATIO_DU",
                {"chat": formula, "de_cho": so_sgk(facts[mole_key]), "dung": so_sgk(predicted)},
            )
    return None, added


_RATIO_MESSAGE = {
    "lech": "Các sản phẩm đã biết cho những mức phản ứng khác nhau, dữ kiện không khớp.",
    "vuot": "Số mol sản phẩm đòi mức phản ứng lớn hơn chất tham gia hết trước, dữ kiện không khớp.",
}


def solve_calc(problem: dict, kb: KnowledgeBase | None = None) -> dict:
    kb = kb or get_kb()
    steps: list[dict] = []
    if problem.get("phan_ung"):
        reactants, products = _parse_equation(problem["phan_ung"])
        _require_known(kb, reactants + products, steps)
        compositions = {formula: kb.compounds[formula].comp for formula in reactants + products}
        coefficients = balance(reactants, products, compositions)
        if coefficients is None:
            return _pack(
                {
                    "co_loi_giai": False,
                    "thong_bao": "Phương trình đề cho không bảo toàn nguyên tố.",
                    "vet": steps,
                },
                "loai_3_khong_bao_toan",
            )
        left = [(formula, coefficients[index]) for index, formula in enumerate(reactants)]
        right = [(formula, coefficients[index + len(reactants)]) for index, formula in enumerate(products)]
        conditions: tuple[str, ...] = ()
        balanced = format_equation(left, right)
        _step(
            steps,
            "tien",
            "BAO_TOAN",
            f"Cân bằng phương trình đề cho: {balanced}.",
            "D3_CAN_BANG",
            {"phuong_trinh": balanced},
        )
    else:
        given = problem.get("chat_tham_gia") or []
        _require_known(kb, given, steps)
        goal_formula = problem["tim"]["chat"]
        if goal_formula not in kb.compounds:
            raise ChemError(f"Chất cần tìm {goal_formula} không có trong phạm vi THCS.")
        matched = []
        for reaction in ensure_reactions(kb):
            reactant_set = {formula for formula, _ in reaction.reactants}
            species = reactant_set | {formula for formula, _ in reaction.products}
            if reactant_set == set(given) and goal_formula in species:
                matched.append(reaction)
        if not matched:
            return _pack(
                {
                    "co_loi_giai": False,
                    "thong_bao": "Không có luật R2 nào cho đúng các chất tham gia này và chất cần tìm.",
                    "vet": steps,
                },
                "loai_3_khong_co_luat",
                {"chat_tham_gia": ", ".join(given), "chat_dich": goal_formula},
            )
        if len(matched) > 1:
            names = [item.text(kb) for item in matched[:8]]
            return _pack(
                {
                    "co_loi_giai": False,
                    "thong_bao": "Có nhiều phản ứng cùng chất tham gia. Cần nêu phương trình trong đề.",
                    "phuong_trinh_ung_vien": names,
                    "vet": steps,
                },
                "loai_3_nhieu_phan_ung",
                {"ung_vien": "; ".join(names)},
            )
        reaction = matched[0]
        left = list(reaction.reactants)
        right = list(reaction.products)
        conditions = reaction.conditions
        equation = reaction.text(kb)
        _step(
            steps,
            "tien",
            reaction.rule_id,
            f"Chọn phản ứng từ luật: {reaction.explain} {equation}.",
            "D3_CHON",
            {"giai_thich": giai_thich_tu_nhien(reaction.explain, reaction.rule_name), "phuong_trinh": equation},
        )
    coeff = {formula: value for formula, value in left + right}
    species = [formula for formula, _ in left + right]
    reactant_names = {formula for formula, _ in left}
    facts: dict[tuple[str, str], Fraction] = {}
    vm = _vm(kb)
    _step(steps, "tien", "C_VM", f"Thể tích mol khí ở đktc Vm = {_show_number(vm)} L/mol.", "C_VM", {"vm": so_sgk(vm)})
    for formula in species:
        mass = molar_mass(kb.compounds[formula].composition, kb.elements)
        parts = " + ".join(
            f"{item['quantity']}×{_show_number(Fraction(str(kb.elements[item['element']]['mass'])))}"
            for item in kb.compounds[formula].composition
        )
        spoken = " + ".join(
            f"{item['quantity']}×{so_sgk(Fraction(str(kb.elements[item['element']]['mass'])))}"
            for item in kb.compounds[formula].composition
        )
        facts[(formula, "M")] = mass
        _step(
            steps,
            "tien",
            "F_MOL_MASS",
            f"M({formula}) = {parts} = {_show_number(mass)} g/mol.",
            "F_MOL_MASS",
            {"chat": formula, "bieu_thuc": spoken, "M": so_sgk(mass)},
        )
    for item in problem.get("biet", []):
        formula = item["chat"]
        quantity = item["dai_luong"]
        if formula not in coeff:
            raise ChemError(f"{formula} không có trong phản ứng vừa lập.")
        facts[(formula, quantity)] = Fraction(str(item["gia_tri"]))
        unit = {"m": "g", "n": "mol", "V": "L", "CM": "mol/L", "Vdd": "L"}.get(quantity, "")
        _step(
            steps,
            "tien",
            "DE_BAI",
            f"Giả thiết: {quantity}({formula}) = {item['gia_tri']} {unit}.",
            "DE_BAI",
            {
                "ten_dai_luong": ten_dai_luong(quantity, formula),
                "gia_tri": so_sgk(facts[(formula, quantity)]),
                "don_vi_chu": don_vi_chu(quantity),
            },
        )
    goal = (problem["tim"]["chat"], problem["tim"]["dai_luong"])
    if goal[0] not in coeff:
        raise ChemError(f"Chất cần tìm {goal[0]} không có trong phản ứng.")
    changed = True
    guard = 0
    stoich_ready = False
    while changed and goal not in facts and guard < 30:
        guard += 1
        changed = False
        for formula in species:
            mass_key = (formula, "m")
            mole_key = (formula, "n")
            molar_key = (formula, "M")
            if mole_key not in facts and mass_key in facts and molar_key in facts:
                value = facts[mass_key] / facts[molar_key]
                facts[mole_key] = value
                _step(
                    steps,
                    "tien",
                    "F_N_MASS",
                    f"n({formula}) = m/M = {_show_number(facts[mass_key])}/{_show_number(facts[molar_key])} = {_show_number(value)} mol.",
                    "F_N_MASS_N",
                    {"chat": formula, "m": so_sgk(facts[mass_key]), "M": so_sgk(facts[molar_key]), "n": so_sgk(value)},
                )
                changed = True
            elif mass_key not in facts and mole_key in facts and molar_key in facts and goal == mass_key:
                value = facts[mole_key] * facts[molar_key]
                facts[mass_key] = value
                _step(
                    steps,
                    "tien",
                    "F_N_MASS",
                    f"m({formula}) = n×M = {_show_number(facts[mole_key])}×{_show_number(facts[molar_key])} = {_show_number(value)} g.",
                    "F_N_MASS_M",
                    {"chat": formula, "n": so_sgk(facts[mole_key]), "M": so_sgk(facts[molar_key]), "m": so_sgk(value)},
                )
                changed = True
            if kb.compounds[formula].state == "khi":
                volume_key = (formula, "V")
                if mole_key not in facts and volume_key in facts:
                    value = facts[volume_key] / vm
                    facts[mole_key] = value
                    _step(
                        steps,
                        "tien",
                        "F_N_VOLUME",
                        f"n({formula}) = V/Vm = {_show_number(facts[volume_key])}/{_show_number(vm)} = {_show_number(value)} mol.",
                        "F_N_VOLUME_N",
                        {"chat": formula, "V": so_sgk(facts[volume_key]), "vm": so_sgk(vm), "n": so_sgk(value)},
                    )
                    changed = True
                elif volume_key not in facts and mole_key in facts and goal == volume_key:
                    value = facts[mole_key] * vm
                    facts[volume_key] = value
                    _step(
                        steps,
                        "tien",
                        "F_N_VOLUME",
                        f"V({formula}) = n×Vm = {_show_number(facts[mole_key])}×{_show_number(vm)} = {_show_number(value)} L.",
                        "F_N_VOLUME_V",
                        {"chat": formula, "n": so_sgk(facts[mole_key]), "vm": so_sgk(vm), "V": so_sgk(value)},
                    )
                    changed = True
            conc_key = (formula, "CM")
            solution_key = (formula, "Vdd")
            if mole_key not in facts and conc_key in facts and solution_key in facts:
                value = facts[conc_key] * facts[solution_key]
                facts[mole_key] = value
                _step(
                    steps,
                    "tien",
                    "F_N_CM",
                    f"n({formula}) = CM×Vdd = {_show_number(facts[conc_key])}×{_show_number(facts[solution_key])} = {_show_number(value)} mol.",
                    "F_N_CM_N",
                    {
                        "chat": formula,
                        "CM": so_sgk(facts[conc_key]),
                        "Vdd": so_sgk(facts[solution_key]),
                        "n": so_sgk(value),
                    },
                )
                changed = True
            elif conc_key not in facts and mole_key in facts and solution_key in facts:
                value = facts[mole_key] / facts[solution_key]
                facts[conc_key] = value
                _step(
                    steps,
                    "tien",
                    "F_N_CM",
                    f"CM({formula}) = n/Vdd = {_show_number(facts[mole_key])}/{_show_number(facts[solution_key])} = {_show_number(value)} mol/L.",
                    "F_N_CM_CM",
                    {
                        "chat": formula,
                        "n": so_sgk(facts[mole_key]),
                        "Vdd": so_sgk(facts[solution_key]),
                        "CM": so_sgk(value),
                    },
                )
                changed = True
            elif solution_key not in facts and mole_key in facts and conc_key in facts:
                value = facts[mole_key] / facts[conc_key]
                facts[solution_key] = value
                _step(
                    steps,
                    "tien",
                    "F_N_CM",
                    f"Vdd({formula}) = n/CM = {_show_number(facts[mole_key])}/{_show_number(facts[conc_key])} = {_show_number(value)} L.",
                    "F_N_CM_VDD",
                    {
                        "chat": formula,
                        "n": so_sgk(facts[mole_key]),
                        "CM": so_sgk(facts[conc_key]),
                        "Vdd": so_sgk(value),
                    },
                )
                changed = True
        if not stoich_ready:
            error, added = _apply_ratio(facts, species, coeff, reactant_names, steps)
            if error:
                _step(steps, "lui", "F_RATIO", _RATIO_MESSAGE[error])
                return _pack(
                    {"co_loi_giai": False, "thong_bao": _RATIO_MESSAGE[error], "vet": steps},
                    f"loai_3_{error}",
                )
            if added is not None:
                stoich_ready = True
                changed = changed or added
    if goal not in facts:
        code, extra, missing = _missing_goal(kb, goal, facts, coeff)
        _step(steps, "lui", "R3", missing)
        return _pack({"co_loi_giai": False, "thong_bao": missing, "vet": steps}, code, extra)
    unit = {"m": "g", "n": "mol", "V": "L", "CM": "mol/L", "Vdd": "L", "M": "g/mol"}[goal[1]]
    return _pack(
        {
            "co_loi_giai": True,
            "ket_qua": _show_number(facts[goal]),
            "don_vi": unit,
            "dai_luong": f"{goal[1]}({goal[0]})",
            "vet": steps,
        },
        "loai_3_thanh_cong",
        {
            "ten_dai_luong": ten_dai_luong(goal[1], goal[0]),
            "ket_qua": so_sgk(facts[goal]),
            "don_vi_chu": don_vi_chu(goal[1]),
        },
    )


def _missing_goal(kb: KnowledgeBase, goal: tuple[str, str], facts: dict, coeff: dict) -> tuple[str, dict, str]:
    formula, quantity = goal
    spoken = ten_dai_luong(quantity, formula)
    if quantity == "V" and kb.compounds[formula].state != "khi":
        return (
            "loai_3_khong_khi",
            {"chat": formula, "trang_thai": viet_thuong(kb.compounds[formula].state_label)},
            f"Luật thể tích khí chỉ áp dụng cho chất khí. {formula} có trạng thái {kb.compounds[formula].state_label}.",
        )
    if (formula, "n") not in facts:
        return (
            "loai_3_thieu_mol",
            {"chat": formula, "ten_dai_luong": spoken},
            (
                f"Suy diễn lùi: để có {quantity}({formula}) cần số mol của {formula}. "
                "Số mol chưa suy ra được từ khối lượng, thể tích khí, nồng độ mol hoặc tỉ lệ hệ số."
            ),
        )
    if quantity == "m":
        return (
            "loai_3_thieu_m",
            {"chat": formula},
            f"Suy diễn lùi: đã có số mol của {formula} nhưng thiếu khối lượng mol để tính khối lượng.",
        )
    if quantity == "CM":
        return (
            "loai_3_thieu_vdd",
            {"chat": formula},
            f"Suy diễn lùi: đã có số mol của {formula} nhưng thiếu thể tích dung dịch Vdd.",
        )
    if quantity == "Vdd":
        return (
            "loai_3_thieu_cm",
            {"chat": formula},
            f"Suy diễn lùi: đã có số mol của {formula} nhưng thiếu nồng độ mol CM để tính thể tích dung dịch.",
        )
    return (
        "loai_3_thieu_khac",
        {"ten_dai_luong": spoken},
        f"Chưa đủ dữ kiện để tính {quantity}({formula}).",
    )


def solve(problem: dict) -> dict:
    kb = get_kb()
    kind = problem.get("loai")
    try:
        if kind == 1:
            result = solve_balance(problem["phan_ung"], kb)
        elif kind == 2:
            result = solve_chain(
                problem["chat_dau"],
                problem["chat_dich"],
                kb,
                problem.get("che_do", "tat_ca"),
                problem.get("chat_cho_phep"),
            )
        elif kind == 3:
            result = solve_calc(problem, kb)
        else:
            result = _pack(
                {"co_loi_giai": False, "thong_bao": "loai phải là 1, 2 hoặc 3.", "vet": []},
                "loai_sai",
            )
    except ChemError as error:
        result = _pack(
            {"co_loi_giai": False, "thong_bao": str(error), "vet": []},
            "loi",
            {"ly_do": str(error).rstrip(".")},
        )
    return _cong_bo(problem, result)
