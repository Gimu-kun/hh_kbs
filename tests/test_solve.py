import unittest

from cstt.infer import solve
from cstt.kb import load_kb
from cstt.reactions import ground_reactions


class SolveTests(unittest.TestCase):
    def test_balance_conserves_atoms(self):
        result = solve({"loai": 1, "phan_ung": "Al2O3 + HCl -> AlCl3 + H2O"})
        self.assertTrue(result["co_loi_giai"])
        self.assertEqual(result["phuong_trinh"], "Al2O3 + 6HCl → 2AlCl3 + 3H2O")
        self.assertTrue(any(step["luat"] == "BAO_TOAN" for step in result["vet"]))

    def test_impossible_balance(self):
        result = solve({"loai": 1, "phan_ung": "H2O -> H2 + NaCl"})
        self.assertFalse(result["co_loi_giai"])

    def test_chain_is_derived(self):
        result = solve({"loai": 2, "chat_dau": "Cu", "chat_dich": "Cu(OH)2"})
        self.assertTrue(result["co_loi_giai"])
        self.assertLessEqual(result["so_buoc"], 5)
        self.assertIn("Cu(OH)2", result["chuoi"][-1])
        self.assertTrue(result["chuoi"][0].startswith("Cu"))

    def test_chain_can_be_limited_to_given_reagents(self):
        opened = solve({"loai": 2, "chat_dau": "Cu", "chat_dich": "Cu(OH)2", "che_do": "tat_ca"})
        closed = solve(
            {
                "loai": 2,
                "chat_dau": "Cu",
                "chat_dich": "Cu(OH)2",
                "che_do": "cho_truoc",
                "chat_cho_phep": ["O2", "HCl", "NaOH"],
            }
        )
        blocked = solve(
            {
                "loai": 2,
                "chat_dau": "Cu",
                "chat_dich": "Cu(OH)2",
                "che_do": "cho_truoc",
                "chat_cho_phep": ["O2"],
            }
        )
        self.assertTrue(opened["co_loi_giai"])
        self.assertTrue(closed["co_loi_giai"])
        self.assertEqual(closed["che_do"], "cho_truoc")
        self.assertNotIn("AgNO3", " ".join(closed["chuoi"]))
        self.assertFalse(blocked["co_loi_giai"])
        heated = solve(
            {
                "loai": 2,
                "chat_dau": "CaCO3",
                "chat_dich": "CaO",
                "che_do": "cho_truoc",
                "chat_cho_phep": [],
            }
        )
        self.assertEqual(heated["chuoi"], ["CaCO3 →[t°] CaO + CO2"])

    def test_unreachable_chain(self):
        result = solve({"loai": 2, "chat_dau": "Ag", "chat_dich": "Na"})
        self.assertFalse(result["co_loi_giai"])

    def test_gas_volume_from_mass(self):
        result = solve(
            {
                "loai": 3,
                "chat_tham_gia": ["Zn", "HCl"],
                "biet": [{"chat": "Zn", "dai_luong": "m", "gia_tri": 6.5}],
                "tim": {"chat": "H2", "dai_luong": "V"},
            }
        )
        self.assertTrue(result["co_loi_giai"])
        self.assertEqual(result["ket_qua"], "2.24")
        self.assertTrue(any(step["luat"] == "F_N_MASS" for step in result["vet"]))
        self.assertTrue(any(step["luat"] == "F_RATIO" for step in result["vet"]))

    def test_salt_mass_and_limiting_reagent(self):
        salt = solve(
            {
                "loai": 3,
                "chat_tham_gia": ["NaOH", "CuSO4"],
                "biet": [{"chat": "NaOH", "dai_luong": "m", "gia_tri": 4}],
                "tim": {"chat": "Na2SO4", "dai_luong": "m"},
            }
        )
        self.assertEqual(salt["ket_qua"], "7.1")
        limited = solve(
            {
                "loai": 3,
                "phan_ung": "Zn + HCl -> ZnCl2 + H2",
                "biet": [
                    {"chat": "Zn", "dai_luong": "n", "gia_tri": 0.2},
                    {"chat": "HCl", "dai_luong": "n", "gia_tri": 0.1},
                ],
                "tim": {"chat": "H2", "dai_luong": "n"},
            }
        )
        self.assertEqual(limited["ket_qua"], "0.05")

    def test_balance_is_symmetric(self):
        forward = solve({"loai": 1, "phan_ung": "Fe + HCl -> FeCl2 + H2"})
        backward = solve({"loai": 1, "phan_ung": "FeCl2 + H2 -> Fe + HCl"})
        self.assertEqual(forward["phuong_trinh"], "Fe + 2HCl → FeCl2 + H2")
        self.assertEqual(backward["phuong_trinh"], "FeCl2 + H2 → Fe + 2HCl")

    def test_chain_keeps_the_element_being_prepared(self):
        sulfur = solve({"loai": 2, "chat_dau": "S", "chat_dich": "H2SO4"})
        self.assertTrue(sulfur["co_loi_giai"])
        self.assertTrue(sulfur["chuoi"][0].startswith("S"))
        self.assertIn("SO3", " ".join(sulfur["chuoi"]))
        self.assertIn("H2SO4", sulfur["chuoi"][-1])
        sodium = solve({"loai": 2, "chat_dau": "NaCl", "chat_dich": "Na"})
        self.assertTrue(sodium["co_loi_giai"])
        self.assertIn("Na", sodium["chuoi"][-1])
        chlorine = solve({"loai": 2, "chat_dau": "NaCl", "chat_dich": "Cl2"})
        self.assertTrue(chlorine["co_loi_giai"])
        self.assertIn("Cl2", chlorine["chuoi"][-1])
        water = solve({"loai": 2, "chat_dau": "H2O", "chat_dich": "Na"})
        self.assertFalse(water["co_loi_giai"])
        iron = solve({"loai": 2, "chat_dau": "Fe", "chat_dich": "Cu"})
        self.assertTrue(iron["co_loi_giai"])
        self.assertEqual(iron["so_buoc"], 1)
        self.assertTrue(iron["chuoi"][0].startswith("Fe"))
        self.assertIn("Cu", iron["chuoi"][0])
        onward = solve({"loai": 2, "chat_dau": "Fe", "chat_dich": "Cu(OH)2"})
        self.assertTrue(onward["co_loi_giai"])
        self.assertTrue(onward["chuoi"][0].startswith("Fe"))
        self.assertIn("Cu(OH)2", onward["chuoi"][-1])
        prepared = solve({"loai": 2, "chat_dau": "Fe", "chat_dich": "CuCl2"})
        self.assertTrue(prepared["co_loi_giai"])
        self.assertNotIn("CuCl2 →", " ".join(prepared["chuoi"][1:]))
        self.assertFalse(any("CuCl2" in step and step.startswith("Fe") for step in prepared["chuoi"]))

    def test_ratio_runs_from_a_known_product(self):
        result = solve(
            {
                "loai": 3,
                "phan_ung": "Zn + HCl -> ZnCl2 + H2",
                "biet": [{"chat": "H2", "dai_luong": "V", "gia_tri": 2.24}],
                "tim": {"chat": "ZnCl2", "dai_luong": "m"},
            }
        )
        self.assertTrue(result["co_loi_giai"])
        self.assertEqual(result["ket_qua"], "13.6")
        self.assertTrue(any("sản phẩm đã biết" in step["noi_dung"] for step in result["vet"]))

    def test_product_amount_can_leave_a_reactant_in_excess(self):
        result = solve(
            {
                "loai": 3,
                "phan_ung": "Zn + HCl -> ZnCl2 + H2",
                "biet": [
                    {"chat": "Zn", "dai_luong": "n", "gia_tri": 0.2},
                    {"chat": "H2", "dai_luong": "V", "gia_tri": 2.24},
                ],
                "tim": {"chat": "ZnCl2", "dai_luong": "n"},
            }
        )
        self.assertEqual(result["ket_qua"], "0.1")
        self.assertTrue(any("Zn dư" in step["noi_dung"] for step in result["vet"]))

    def test_conflicting_amounts_are_rejected(self):
        too_much_product = solve(
            {
                "loai": 3,
                "phan_ung": "Zn + HCl -> ZnCl2 + H2",
                "biet": [
                    {"chat": "HCl", "dai_luong": "n", "gia_tri": 0.1},
                    {"chat": "H2", "dai_luong": "n", "gia_tri": 0.1},
                ],
                "tim": {"chat": "ZnCl2", "dai_luong": "n"},
            }
        )
        self.assertFalse(too_much_product["co_loi_giai"])
        disagreed = solve(
            {
                "loai": 3,
                "phan_ung": "Zn + HCl -> ZnCl2 + H2",
                "biet": [
                    {"chat": "ZnCl2", "dai_luong": "n", "gia_tri": 0.2},
                    {"chat": "H2", "dai_luong": "n", "gia_tri": 0.1},
                ],
                "tim": {"chat": "Zn", "dai_luong": "n"},
            }
        )
        self.assertFalse(disagreed["co_loi_giai"])

    def test_solution_volume_from_moles_and_concentration(self):
        result = solve(
            {
                "loai": 3,
                "phan_ung": "Zn + HCl -> ZnCl2 + H2",
                "biet": [
                    {"chat": "HCl", "dai_luong": "n", "gia_tri": 0.1},
                    {"chat": "HCl", "dai_luong": "CM", "gia_tri": 0.5},
                ],
                "tim": {"chat": "HCl", "dai_luong": "Vdd"},
            }
        )
        self.assertEqual(result["ket_qua"], "0.2")
        self.assertEqual(result["don_vi"], "L")

    def test_rules_cover_core_without_stored_paths(self):
        kb = load_kb()
        reactions = ground_reactions(kb)
        self.assertGreater(len(reactions), 100)
        self.assertTrue(any(item.rule_id == "R2_TRUNG_HOA" for item in reactions))
        self.assertFalse(any(rule.get("kind") == "instance" or "items" in rule for rule in kb.r2["rules"]))
        rule_keys = {frozenset(rule) for rule in kb.r2["rules"]}
        self.assertEqual(len(rule_keys), 1)
        when_keys = {frozenset(item["when"]) for item in kb.r1["solubility"]}
        self.assertEqual(len(when_keys), 1)
        formula_keys = {frozenset(item) for item in kb.formulas["items"]}
        self.assertEqual(len(formula_keys), 1)
        zinc = next(item for item in reactions if item.reactants[0][0] == "Zn" and any(f == "NaOH" for f, _ in item.reactants))
        self.assertEqual(zinc.text(kb), "Zn + 2NaOH → Na2ZnO2 + H2")
        self.assertIn("H2O", kb.compounds)
        self.assertEqual(kb.compounds["H2O"].state, "long")
        self.assertEqual(kb.compounds["NaAlO2"].class_id, "muoi_trung_hoa")
        self.assertEqual(kb.compounds["NH4NO3"].class_id, "muoi_trung_hoa")


if __name__ == "__main__":
    unittest.main()
