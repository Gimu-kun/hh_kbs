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
def knowledge():
    return KnowledgeBase(ROOT / "data")


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
        f"tái tạo {report['correct']}/{report['total']} = {report['rate']:.2%}; "
        f"sai {report['wrong']}; không sinh {report['missing']}; sinh thêm {report['extra']}"
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
    result = engine.chain("Na", "NaCl", 3)
    assert result["found"] is True
    assert any(step["pending"] for step in result["reactions"])
    assert "chưa được kiểm duyệt" in result["explanation"]


@pytest.fixture()
def client(tmp_path):
    data_copy = tmp_path / "data"
    shutil.copytree(ROOT / "data", data_copy)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("KBS_DATA_DIR", str(data_copy))
    with TestClient(app) as test_client:
        yield test_client
    monkeypatch.undo()


def test_admin_review_api(client):
    denied = client.get("/api/v1/admin/reviews")
    assert denied.status_code == 401
    bad = client.post("/api/v1/auth/login", json={"username": "admin", "password": "sai"})
    assert bad.status_code == 401
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "hh-admin"})
    assert login.status_code == 200
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    chain = client.post("/api/v1/solve/chain", json={"start": "Cu", "target": "Cu(OH)2", "max_steps": 6})
    assert chain.status_code == 200
    body = chain.json()
    assert body["found"] is True
    pending = [step for step in body["reactions"] if step["pending"]]
    assert pending, body["explanation"]
    assert "chưa được kiểm duyệt" in body["explanation"]
    review_id = pending[0]["review_id"]
    rejected = client.post(
        f"/api/v1/admin/reviews/{review_id}/reject",
        headers=headers,
        json={"note": "không dùng phản ứng này trong lời giải", "rule_fault": True},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["rule_id"]
    listed = client.get("/api/v1/admin/reviews", headers=headers, params={"status": "rejected"})
    assert listed.status_code == 200
    assert any(item["id"] == review_id for item in listed.json()["items"])
