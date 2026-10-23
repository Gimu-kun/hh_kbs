"""Suy diễn tiến, heuristic H2/H4/H5, kiểm duyệt và các ví dụ chuỗi."""

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.audit import audit_reference
from app.core.chain_search import find_chain
from app.core.forward import propose
from app.core.species import Catalog
from app.main import app
from app.services.inference import InferenceEngine
from app.services.knowledge_base import KnowledgeBase
from app.services.reviews import ReviewStore

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    dest = tmp_path_factory.mktemp("kbs") / "data"
    shutil.copytree(ROOT / "data", dest)
    return dest


@pytest.fixture(scope="module")
def knowledge(data_dir):
    return KnowledgeBase(data_dir)


@pytest.fixture(scope="module")
def catalog(knowledge):
    series = next(
        item["series"] for item in knowledge.heuristics.list() if item.get("kind") == "activity_series"
    )
    return Catalog(knowledge.compounds.list(), knowledge.elements.list(), series)


@pytest.fixture(scope="module")
def rules(knowledge):
    return knowledge.rules.list()


def test_reproduction_reaches_eighty_percent(rules, catalog):
    reactions = json.loads((ROOT / "tests" / "fixtures" / "reference_reactions.json").read_text(encoding="utf-8"))
    report = audit_reference(reactions["items"], rules, catalog)
    print(
        f"ứng viên đầu {report['correct']}/{report['total']} = {report['rate']:.2%}; "
        f"lỏng {report['loose']}/{report['total']} = {report['loose_rate']:.2%}; "
        f"một đáp án {report['single']}/{report['total']} = {report['single_rate']:.2%}; "
        f"sai {report['wrong']}; không sinh {report['missing']}"
    )
    assert report["correct"] >= 690
    assert report["rate"] >= 0.80


def test_examples_still_solve(knowledge):
    engine = InferenceEngine(knowledge)
    expected = {
        ("Cu", "Cu(OH)2"): True,
        ("CaCO3", "CaCl2"): True,
        ("Na", "NaCl"): True,
        ("S", "H2SO4"): True,
        ("Au", "NaCl"): True,
        ("Fe2O3", "Fe"): True,
    }
    for (start, target), found in expected.items():
        result = engine.chain(start, target, 6)
        assert result["found"] is found, result["explanation"]
        assert result["reactions"]
        assert all(step["rule_id"] for step in result["reactions"])
    balance = engine.balance("Fe2O3 + H2 → Fe + H2O")
    assert balance["balanced"] == "Fe2O3 + 3H2 → 2Fe + 3H2O"
    quantity = engine.quantity(
        {
            "equation": "Al + H2SO4 → Al2(SO4)3 + H2",
            "known": {"formula": "Al", "kind": "mass", "value": 5.4},
            "find": {"formula": "Al2(SO4)3", "kind": "mass"},
        }
    )
    assert quantity["find"]["display"] == "34,2 g"


def test_chain_does_not_read_reaction_store(knowledge, monkeypatch):
    engine = InferenceEngine(knowledge)

    def explode():
        raise AssertionError("bộ suy diễn không được đọc reactions.json")

    monkeypatch.setattr(engine.knowledge.reactions, "list", explode)
    result = engine.chain("Na", "NaCl", 4)
    assert result["found"] is True


def test_activity_series_blocks_weaker_metal(rules, catalog):
    zinc = propose(["Zn", "CuSO4"], "NONE", rules, catalog)
    copper = propose(["Cu", "ZnSO4"], "NONE", rules, catalog)
    assert any("Cu" in item["products"] for item in zinc)
    assert not any("Zn" in item["products"] for item in copper)


def test_h2_weight_changes_ranking():
    graph = {
        "A": [
            {"to": "B", "penalty": 0, "aux_count": 5, "from_class": "", "to_class": ""},
            {"to": "C", "penalty": 5, "aux_count": 0, "from_class": "", "to_class": ""},
        ],
        "B": [{"to": "Z", "penalty": 0, "aux_count": 0, "from_class": "", "to_class": ""}],
        "C": [{"to": "Z", "penalty": 0, "aux_count": 0, "from_class": "", "to_class": ""}],
    }
    with_weight = find_chain("A", "Z", graph, 4, h2_weight=1)
    without_weight = find_chain("A", "Z", graph, 4, h2_weight=0)
    assert [edge["to"] for edge in with_weight] == ["B", "Z"]
    assert [edge["to"] for edge in without_weight] == ["C", "Z"]


def test_h4_prefers_step_closer_to_target_class():
    pattern = ["don_chat_kim_loai", "oxit_bazo", "bazo", "muoi"]
    graph = {
        "CaO": [
            {"to": "Ca", "penalty": 0, "aux_count": 0, "from_class": "oxit_bazo", "to_class": "don_chat_kim_loai"},
            {"to": "Ca(OH)2", "penalty": 0, "aux_count": 0, "from_class": "oxit_bazo", "to_class": "bazo"},
        ],
        "Ca": [{"to": "CaCl2", "penalty": 0, "aux_count": 0, "from_class": "don_chat_kim_loai", "to_class": "muoi"}],
        "Ca(OH)2": [{"to": "CaCl2", "penalty": 0, "aux_count": 0, "from_class": "bazo", "to_class": "muoi"}],
    }
    path = find_chain("CaO", "CaCl2", graph, 4, pattern=pattern, target_class="muoi")
    assert path[0]["to"] == "Ca(OH)2"


def test_pending_step_is_marked_and_reject_blocks_reuse(tmp_path, rules, catalog):
    store = ReviewStore(tmp_path, reference_path=tmp_path / "missing.json")
    reaction = {
        "condition": "NONE",
        "reactants": ["Zn", "CuSO4"],
        "products": ["ZnSO4", "Cu"],
        "coefficients": [1, 1, 1, 1],
        "rule_id": "L14",
        "rule_text": "Kim loại đẩy kim loại yếu hơn",
    }
    recorded = store.classify_step(reaction, source="solution")
    assert recorded["status"] == "pending"
    rejected = store.reject(recorded["id"], "luật chọn sai hóa trị", rule_fault=True)
    assert rejected["rule_fault"] is True
    assert rejected["rule_id"] == "L14"
    assert store.status_of(["Zn", "CuSO4"], ["ZnSO4", "Cu"], "NONE") == "rejected"
    again = propose(["Zn", "CuSO4"], "NONE", rules, catalog, store.rejected_signatures())
    assert not any(item["products"] == ["ZnSO4", "Cu"] or set(item["products"]) == {"ZnSO4", "Cu"} for item in again)


def test_renderer_marks_unreviewed_step(knowledge, tmp_path):
    engine = InferenceEngine(knowledge)
    engine.reviews = ReviewStore(tmp_path, reference_path=tmp_path / "missing.json")
    result = engine.chain("Na", "NaCl", 3, allow_pending=True)
    assert result["found"] is True
    assert any(step["pending"] for step in result["reactions"])
    assert "chưa được kiểm duyệt" in result["explanation"]


@pytest.fixture()
def client(tmp_path):
    data_copy = tmp_path / "data"
    shutil.copytree(ROOT / "data", data_copy)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("KBS_DATA_DIR", str(data_copy))
    monkeypatch.setenv("KBS_ADMIN_PASSWORD", "kbs-test-pass")
    with TestClient(app) as test_client:
        test_client.data_dir = data_copy
        yield test_client
    monkeypatch.undo()


def _admin_headers(client):
    blocked = client.post(
        "/api/v1/compounds",
        json={"formula": "Xx", "name": "Thử", "class": "don_chat_phi_kim", "state": "ran", "soluble": "khong_tan", "charge": 0},
    )
    assert blocked.status_code == 401
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "kbs-test-pass"})
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True
    first = {"Authorization": f"Bearer {login.json()['token']}"}
    assert client.get("/api/v1/admin/reviews", headers=first).status_code == 403
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=first,
        json={"current_password": "kbs-test-pass", "new_password": "kbs-test-pass-2"},
    )
    assert changed.status_code == 200
    again = client.post("/api/v1/auth/login", json={"username": "admin", "password": "kbs-test-pass-2"})
    return {"Authorization": f"Bearer {again.json()['token']}"}


def test_admin_review_api(client):
    denied = client.get("/api/v1/admin/reviews")
    assert denied.status_code == 401
    bad = client.post("/api/v1/auth/login", json={"username": "admin", "password": "sai"})
    assert bad.status_code == 401
    headers = _admin_headers(client)
    reviews_path = Path(client.data_dir) / "reaction_reviews.json"
    before = reviews_path.read_bytes()
    chain = client.post("/api/v1/solve/chain", json={"start": "Cu", "target": "Cu(OH)2", "max_steps": 6})
    assert chain.status_code == 200
    assert chain.json()["found"] is True
    assert reviews_path.read_bytes() == before
    pending = client.get("/api/v1/admin/reviews", headers=headers, params={"status": "pending"})
    assert pending.status_code == 200
    review_id = pending.json()["items"][0]["id"]
    rejected = client.post(
        f"/api/v1/admin/reviews/{review_id}/reject",
        headers=headers,
        json={"note": "không dùng phản ứng này trong lời giải", "rule_fault": True},
    )
    assert rejected.status_code == 200
    assert rejected.json()["rule_fault"] is True
    blocked = client.post(
        f"/api/v1/admin/reviews/{review_id}/approve",
        headers=headers,
        json={"note": "mở lại"},
    )
    assert blocked.status_code == 400
    reopened = client.post(
        f"/api/v1/admin/reviews/{review_id}/reopen",
        headers=headers,
        json={"note": "xem lại"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "pending"
    assert any(entry["rule_fault"] for entry in reopened.json()["history"])
    logged_out = client.post("/api/v1/auth/logout", headers=headers)
    assert logged_out.status_code == 200
    assert client.get("/api/v1/admin/reviews", headers=headers).status_code == 401


def test_forbidden_reactions_are_not_generated(rules, catalog):
    empty = [
        (["N2", "H2SO4"], "CONC"),
        (["N2", "H2SO4"], "CONC_HEAT"),
        (["H3PO4", "Na2SO4"], "NONE"),
        (["H2S", "Na2SO4"], "NONE"),
    ]
    for reactants, condition in empty:
        assert propose(reactants, condition, rules, catalog) == []
    iron = propose(["FeCl2", "H2SO4"], "CONC_HEAT", rules, catalog)
    assert iron
    assert all("SO2" in item["products"] and "Fe2(SO4)3" in item["products"] for item in iron)
    assert all("H2S" not in item["products"] for item in iron)
    carbonate = propose(["CaCO3", "HCl"], "NONE", rules, catalog)
    assert carbonate
    assert all("Ca(HCO3)2" not in item["products"] for item in carbonate)
    for formula in ("Ca(HCO3)2", "Ba(HCO3)2"):
        metal = formula[:2]
        products = propose([formula, "NaOH"], "NONE", rules, catalog)
        assert all(f"{metal}(OH)2" not in item["products"] for item in products)
    for metal in ("Fe", "Zn", "Cu"):
        oxidized = propose([metal, "H2SO4"], "CONC_HEAT", rules, catalog)
        assert all("H2S" not in item["products"] for item in oxidized)
    cold = propose(["Cl2", "NaOH"], "NONE", rules, catalog)
    hot = propose(["Cl2", "NaOH"], "HEAT", rules, catalog)
    assert any("NaClO" in item["products"] for item in cold)
    assert all("NaClO3" not in item["products"] for item in cold)
    assert any("NaClO3" in item["products"] for item in hot)
    assert all("NaClO" not in item["products"] for item in hot)


def test_requested_chain_routes(knowledge):
    engine = InferenceEngine(knowledge)
    sulfur = engine.chain("S", "SO3", 6)
    assert sulfur["found"], sulfur["explanation"]
    sulfur_text = " ".join(step["equation"] for step in sulfur["reactions"])
    assert "SO2" in sulfur_text and "SO3" in sulfur_text and "V2O5" in sulfur_text

    nitrogen = engine.chain("N2", "HNO3", 8)
    assert nitrogen["found"], nitrogen["explanation"]
    nitrogen_text = " ".join(step["equation"] for step in nitrogen["reactions"])
    assert "NH3" in nitrogen_text or "NO" in nitrogen_text
    assert nitrogen["reactions"][-1]["to"] == "HNO3"

    lime = engine.chain("CaCO3", "Ca(OH)2", 6)
    assert lime["found"], lime["explanation"]
    assert any("CaO" in step["products"] for step in lime["reactions"])
    assert any(step["condition"] == "HEAT" for step in lime["reactions"])
    assert "t°" in lime["explanation"]

    copper = engine.chain("Cu", "Cu(OH)2", 6)
    assert copper["found"], copper["explanation"]
    copper_text = " ".join(step["equation"] for step in copper["reactions"])
    assert "FeCl2" not in copper_text
    assert "Cu(OH)2" in copper_text
