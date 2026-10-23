"""Kiểm thử cân bằng, đại lượng, chuỗi phản ứng và API."""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.balancer import balance_formulas
from app.core.formula import parse_equation, parse_formula
from app.main import app
from app.services.inference import InferenceEngine
from app.services.knowledge_base import KnowledgeBase

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    dest = tmp_path_factory.mktemp("solver") / "data"
    shutil.copytree(ROOT / "data", dest)
    return InferenceEngine(KnowledgeBase(dest))


def test_formula_parentheses():
    assert parse_formula("Fe2(SO4)3") == {"Fe": 2, "S": 3, "O": 12}
    assert parse_formula("Ca(OH)2") == {"Ca": 1, "O": 2, "H": 2}
    assert parse_formula("(NH4)2SO4") == {"N": 2, "H": 8, "S": 1, "O": 4}


@pytest.mark.parametrize(
    ("equation", "expected"),
    [
        ("MgCl2 + KOH → Mg(OH)2 + KCl", "MgCl2 + 2KOH → Mg(OH)2 + 2KCl"),
        ("P + O2 → P2O5", "4P + 5O2 → 2P2O5"),
        ("NO2 + O2 + H2O → HNO3", "4NO2 + O2 + 2H2O → 4HNO3"),
        ("P2O5 + H2O → H3PO4", "P2O5 + 3H2O → 2H3PO4"),
        ("Al + H2SO4 → Al2(SO4)3 + H2", "2Al + 3H2SO4 → Al2(SO4)3 + 3H2"),
        ("KMnO4 → K2MnO4 + MnO2 + O2", "2KMnO4 → K2MnO4 + MnO2 + O2"),
        ("Fe2O3 + H2 → Fe + H2O", "Fe2O3 + 3H2 → 2Fe + 3H2O"),
    ],
)
def test_balance_samples(engine, equation, expected):
    result = engine.balance(equation)
    assert result["balanced"] == expected
    assert "\n" in result["explanation"]
    assert result["explanation"].startswith("Bước 1:")
    assert "Bước 2:" in result["explanation"]


def test_quantity_mass_and_volume(engine):
    zinc_salt = engine.quantity(
        {
            "equation": "Zn + HCl → ZnCl2 + H2",
            "known": {"formula": "Zn", "kind": "mass", "value": 13},
            "find": {"formula": "ZnCl2", "kind": "mass"},
        }
    )
    assert zinc_salt["find"]["display"] == "27,2 g"
    assert "nZnCl2 = nZn = 0,2 mol" in zinc_salt["explanation"]

    hydrogen = engine.quantity(
        {
            "equation": "Zn + HCl → ZnCl2 + H2",
            "known": {"formula": "Zn", "kind": "mass", "value": 13},
            "find": {"formula": "H2", "kind": "volume"},
        }
    )
    assert hydrogen["find"]["display"] == "4,48 lít"

    iron = engine.quantity(
        {
            "equation": "Fe2O3 + H2 → Fe + H2O",
            "known": {"formula": "Fe2O3", "kind": "mass", "value": 16},
            "find": {"formula": "Fe", "kind": "mass"},
        }
    )
    assert iron["find"]["display"] == "11,2 g"

    aluminium = engine.quantity(
        {
            "equation": "Al + H2SO4 → Al2(SO4)3 + H2",
            "known": {"formula": "Al", "kind": "mass", "value": 5.4},
            "find": {"formula": "Al2(SO4)3", "kind": "mass"},
        }
    )
    assert aluminium["find"]["display"] == "34,2 g"
    assert "1/2" in aluminium["explanation"]


def test_chains_reach_target_and_show_condition(engine):
    cases = [
        ("Na", "NaCl"),
        ("CaCO3", "CaCl2"),
        ("CaCO3", "Ca(OH)2"),
        ("S", "H2SO4"),
        ("Cu", "Cu(OH)2"),
        ("Fe2O3", "Fe"),
        ("Zn", "Cu"),
        ("P", "H3PO4"),
    ]
    for start, target in cases:
        result = engine.chain(start, target, 6)
        assert result["found"], result["explanation"]
        assert result["reactions"][-1]["to"] == target
        assert result["reactions"][0]["from"] == start
        text = result["explanation"]
        assert "\n" in text
        assert "Phương trình:" in text
        assert "Điều kiện:" in text


def test_activity_series_follows_textbook(engine):
    elements = engine.knowledge.element_map()
    order = ["K", "Ba", "Ca", "Na", "Mg", "Al", "Zn", "Fe", "Ni", "Sn", "Pb", "H", "Cu", "Hg", "Ag", "Pt", "Au"]
    activities = [elements[symbol]["activity"] for symbol in order]
    assert activities == list(range(1, len(order) + 1))


def test_imported_reactions_conserve_atoms():
    # Bộ suy diễn không đọc reactions.json. Hệ số của bộ tham chiếu vẫn phải
    # khớp bộ cân bằng đại số, nên kiểm tra đọc fixture.
    import json

    reactions = json.loads((ROOT / "tests" / "fixtures" / "reference_reactions.json").read_text(encoding="utf-8"))
    for reaction in reactions["items"]:
        reactants, products = reaction["reactants"], reaction["products"]
        balanced = balance_formulas(reactants, products)
        assert reaction["coefficients"] == balanced["coefficients"]


@pytest.fixture()
def client(tmp_path):
    data_copy = tmp_path / "data"
    shutil.copytree(ROOT / "data", data_copy)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("KBS_DATA_DIR", str(data_copy))
    monkeypatch.setenv("KBS_ADMIN_PASSWORD", "kbs-test-pass")
    with TestClient(app) as test_client:
        yield test_client
    monkeypatch.undo()


def test_api_solvers_and_crud(client):
    health = client.get("/api/v1/health")
    assert health.status_code == 200

    meta = client.get("/api/v1/meta")
    assert meta.status_code == 200
    assert meta.json()["counts"]["elements"] >= 100

    balance = client.post("/api/v1/solve/balance", json={"equation": "Al + O2 → Al2O3"})
    assert balance.status_code == 200
    assert balance.json()["balanced"] == "4Al + 3O2 → 2Al2O3"

    chain = client.post("/api/v1/solve/chain", json={"start": "CaCO3", "target": "Ca(OH)2", "max_steps": 6})
    assert chain.status_code == 200
    body = chain.json()
    assert body["found"] is True
    assert any("CaO" in step["products"] for step in body["reactions"])
    assert any(step["condition"] == "HEAT" for step in body["reactions"])
    assert "t°" in body["explanation"]
    assert "Khớp luật" in body["explanation"]

    quantity = client.post(
        "/api/v1/solve/quantity",
        json={
            "equation": "Zn + HCl → ZnCl2 + H2",
            "known": {"formula": "Zn", "kind": "mass", "value": 13},
            "find": {"formula": "H2", "kind": "volume"},
        },
    )
    assert quantity.status_code == 200
    assert quantity.json()["find"]["display"] == "4,48 lít"

    anonymous = client.post(
        "/api/v1/elements",
        json={"symbol": "Xx", "name": "Thử nghiệm", "z": 999, "mass": 10, "valence": [1], "type": "phi_kim"},
    )
    assert anonymous.status_code == 401
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "kbs-test-pass"})
    assert login.status_code == 200
    first = {"Authorization": f"Bearer {login.json()['token']}"}
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=first,
        json={"current_password": "kbs-test-pass", "new_password": "kbs-test-pass-2"},
    )
    assert changed.status_code == 200
    again = client.post("/api/v1/auth/login", json={"username": "admin", "password": "kbs-test-pass-2"})
    headers = {"Authorization": f"Bearer {again.json()['token']}"}
    created = client.post(
        "/api/v1/elements",
        headers=headers,
        json={"symbol": "Xx", "name": "Thử nghiệm", "z": 999, "mass": 10, "valence": [1], "type": "phi_kim"},
    )
    assert created.status_code == 201
    assert client.get("/api/v1/elements/Xx").status_code == 200

    duplicated = client.post(
        "/api/v1/elements",
        headers=headers,
        json={"symbol": "Xx", "name": "Thử nghiệm", "z": 999, "mass": 10, "valence": [1], "type": "phi_kim"},
    )
    assert duplicated.status_code == 409

    compound = client.post(
        "/api/v1/compounds",
        headers=headers,
        json={
            "formula": "Xx2",
            "name": "Đơn chất thử",
            "class": "don_chat_phi_kim",
            "state": "ran",
            "soluble": "khong_tan",
            "charge": 0,
        },
    )
    assert compound.status_code == 201
    blocked = client.delete("/api/v1/elements/Xx", headers=headers)
    assert blocked.status_code == 409
    assert client.delete("/api/v1/compounds/Xx2", headers=headers).status_code == 200
    assert client.delete("/api/v1/elements/Xx", headers=headers).status_code == 200

    bad = client.post("/api/v1/solve/balance", json={"equation": "H2O → H2"})
    assert bad.status_code == 400
