"""Chạy bộ suy diễn hoá vô cơ THCS.

Dạng 1: python3 main.py 1 "Al2O3 + HCl -> AlCl3 + H2O"
Dạng 2, mọi thuốc thử THCS: python3 main.py 2 Cu Cu(OH)2
Dạng 2, chỉ chất cho trước: python3 main.py 2 Cu Cu(OH)2 cho_truoc O2,HCl,NaOH
Dạng 3: python3 main.py 3 Zn,HCl Zn:m=6.5 H2:V
"""

from __future__ import annotations

import json
import sys

from cstt.infer import solve


def _parse_calc(parts: list[str]) -> dict:
    reactants = [item for item in parts[0].split(",") if item]
    known = []
    for item in parts[1:-1]:
        substance, raw = item.split(":", 1)
        quantity, value = raw.split("=", 1)
        known.append({"chat": substance, "dai_luong": quantity, "gia_tri": float(value)})
    goal_substance, goal_quantity = parts[-1].split(":", 1)
    return {
        "loai": 3,
        "chat_tham_gia": reactants,
        "biet": known,
        "tim": {"chat": goal_substance, "dai_luong": goal_quantity},
    }


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        print(__doc__)
        return
    if argv[1].endswith(".json"):
        with open(argv[1], encoding="utf-8") as handle:
            problem = json.load(handle)
    elif argv[1] == "1":
        problem = {"loai": 1, "phan_ung": argv[2]}
    elif argv[1] == "2":
        problem = {"loai": 2, "chat_dau": argv[2], "chat_dich": argv[3], "che_do": "tat_ca"}
        if len(argv) > 4:
            problem["che_do"] = argv[4]
            if argv[4] == "cho_truoc":
                raw = argv[5] if len(argv) > 5 else ""
                problem["chat_cho_phep"] = [item for item in raw.split(",") if item]
    elif argv[1] == "3":
        problem = _parse_calc(argv[2:])
    else:
        print(__doc__)
        return
    result = solve(problem)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv)
