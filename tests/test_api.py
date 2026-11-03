import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from cstt import kb as kb_paths
from cstt.api import app
from cstt.infer import reload_kb
from cstt.kb import CONCEPT, RULES
from cstt.validate import validate_knowledge


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        shutil.copytree(CONCEPT, root / "concept")
        shutil.copytree(RULES, root / "rules")
        self.previous = (kb_paths.CONCEPT, kb_paths.RULES)
        kb_paths.CONCEPT = root / "concept"
        kb_paths.RULES = root / "rules"
        reload_kb()
        self.client = TestClient(app)

    def tearDown(self):
        kb_paths.CONCEPT, kb_paths.RULES = self.previous
        reload_kb()
        self.tmp.cleanup()

    def test_lists_the_knowledge_base(self):
        elements = self.client.get("/api/nguyen-to")
        compounds = self.client.get("/api/hop-chat")
        rules = self.client.get("/api/luat-phan-ung")
        self.assertEqual(elements.status_code, 200)
        self.assertEqual(len(elements.json()), 118)
        self.assertGreater(len(compounds.json()), 100)
        self.assertGreater(len(rules.json()), 20)
        self.assertEqual(self.client.get("/api/do-sau").json(), {"max_depth": 5})
        self.assertEqual(self.client.get("/api/nguyen-to/Na").json()["name"], "Natri")

    def test_crud_round_trip_for_a_condition(self):
        created = self.client.post(
            "/api/dieu-kien",
            json={
                "code": "TEST",
                "name": "Thử",
                "symbol": "thử",
                "complexity": 1,
                "description": "Điều kiện thử.",
            },
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(self.client.get("/api/dieu-kien/TEST").json()["name"], "Thử")
        updated = self.client.put(
            "/api/dieu-kien/TEST",
            json={
                "code": "TEST",
                "name": "Thử đã sửa",
                "symbol": "thử",
                "complexity": 1,
                "description": "Điều kiện thử.",
            },
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(self.client.get("/api/dieu-kien/TEST").json()["name"], "Thử đã sửa")
        duplicate = self.client.post(
            "/api/dieu-kien",
            json={
                "code": "TEST",
                "name": "Trùng",
                "symbol": "",
                "complexity": 1,
                "description": "",
            },
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(self.client.delete("/api/dieu-kien/TEST").status_code, 204)
        self.assertEqual(self.client.get("/api/dieu-kien/TEST").status_code, 404)

    def test_invalid_compound_is_rejected(self):
        before = self.client.get("/api/hop-chat/H2O").json()
        rejected = self.client.post(
            "/api/hop-chat",
            json={
                "formula": "H2O",
                "name": "Nước sai",
                "class": "axit",
                "class_label": "Axit",
                "composition": [{"element": "H", "quantity": 1}, {"element": "O", "quantity": 1}],
                "state": "long",
                "state_label": "Lỏng",
            },
        )
        self.assertEqual(rejected.status_code, 409)
        bad = self.client.put(
            "/api/hop-chat/H2O",
            json={
                "formula": "H2O",
                "name": "Nước",
                "class": "axit",
                "class_label": "Axit",
                "composition": before["composition"],
                "state": "long",
                "state_label": "Lỏng",
            },
        )
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(self.client.get("/api/hop-chat/H2O").json()["class"], "oxit_trung_tinh")

    def test_rejects_duplicates_and_dangling_references(self):
        validate_knowledge()
        element = self.client.get("/api/nguyen-to/He").json()
        element["symbol"] = "Qq"
        element["name"] = "Heli"
        element["z"] = 200
        duplicated_name = self.client.post("/api/nguyen-to", json=element)
        self.assertEqual(duplicated_name.status_code, 422)
        self.assertIn("Tên nguyên tố bị trùng", duplicated_name.json()["detail"])
        element["name"] = "Quang thử"
        element["z"] = 1
        duplicated_z = self.client.post("/api/nguyen-to", json=element)
        self.assertEqual(duplicated_z.status_code, 422)
        self.assertIn("Số hiệu nguyên tử bị trùng", duplicated_z.json()["detail"])
        element["z"] = 200
        created = self.client.post("/api/nguyen-to", json=element)
        self.assertEqual(created.status_code, 201)

        condition = self.client.get("/api/dieu-kien/HEAT").json()
        condition["code"] = "TEST_SYMBOL"
        condition["name"] = "Ký hiệu trùng"
        duplicated_symbol = self.client.post("/api/dieu-kien", json=condition)
        self.assertEqual(duplicated_symbol.status_code, 422)
        self.assertIn("Ký hiệu điều kiện bị trùng", duplicated_symbol.json()["detail"])

        removed_condition = self.client.delete("/api/dieu-kien/HEAT")
        self.assertEqual(removed_condition.status_code, 422)
        self.assertIn("HEAT", removed_condition.json()["detail"])
        self.assertEqual(self.client.get("/api/dieu-kien/HEAT").status_code, 200)

        removed_class = self.client.delete("/api/lop/axit")
        self.assertEqual(removed_class.status_code, 422)
        removed_compound = self.client.delete("/api/hop-chat/H2O")
        self.assertEqual(removed_compound.status_code, 422)
        self.assertEqual(self.client.get("/api/hop-chat/H2O").status_code, 200)

        water = self.client.get("/api/hop-chat/H2O").json()
        water["class_label"] = "Axit"
        relabel = self.client.put("/api/hop-chat/H2O", json=water)
        self.assertEqual(relabel.status_code, 422)

        missing_oxide = self.client.post("/api/oxit-trung-tinh", json={"formula": "CO2"})
        self.assertEqual(missing_oxide.status_code, 422)
        missing_anion = self.client.post("/api/anion-muoi-axit", json={"formula": "XO4"})
        self.assertEqual(missing_anion.status_code, 422)

        solubility = self.client.get("/api/do-tan/SOL_NO3").json()
        solubility["id"] = "SOL_TEST"
        solubility["name"] = "Anion không có"
        solubility["when"]["anion"] = "XO3"
        bad_solubility = self.client.post("/api/do-tan", json=solubility)
        self.assertEqual(bad_solubility.status_code, 422)

        rule = self.client.get("/api/luat-phan-ung/R2_TRUNG_HOA").json()
        rule["id"] = "R2_TEST"
        rule["name"] = "Luật thử lớp không có"
        rule["classes"] = ["khong_co"]
        bad_rule = self.client.post("/api/luat-phan-ung", json=rule)
        self.assertEqual(bad_rule.status_code, 422)
        self.assertIn("khong_co", bad_rule.json()["detail"])

        parent = self.client.get("/api/lop/axit").json()
        parent["children"] = ["oxit_bazo"]
        two_parents = self.client.put("/api/lop/axit", json=parent)
        self.assertEqual(two_parents.status_code, 422)
        self.assertIn("axit", two_parents.json()["detail"])

    def test_solve_endpoints(self):
        balance = self.client.post("/api/giai/can-bang", json={"phan_ung": "Al2O3 + HCl -> AlCl3 + H2O"})
        self.assertEqual(balance.json()["phuong_trinh"], "Al2O3 + 6HCl → 2AlCl3 + 3H2O")
        chain = self.client.post(
            "/api/giai/chuoi",
            json={"chat_dau": "NaCl", "chat_dich": "Na", "che_do": "tat_ca"},
        )
        self.assertTrue(chain.json()["co_loi_giai"])
        self.assertIn("Na", chain.json()["chuoi"][-1])
        amount = self.client.post(
            "/api/giai/tinh",
            json={
                "phan_ung": "Zn + HCl -> ZnCl2 + H2",
                "biet": [{"chat": "Zn", "dai_luong": "m", "gia_tri": 6.5}],
                "tim": {"chat": "H2", "dai_luong": "V"},
            },
        )
        self.assertEqual(amount.json()["ket_qua"], "2.24")
        unified = self.client.post("/api/giai", json={"loai": 1, "phan_ung": "Fe + HCl -> FeCl2 + H2"})
        self.assertEqual(unified.json()["phuong_trinh"], "Fe + 2HCl → FeCl2 + H2")


if __name__ == "__main__":
    unittest.main()
