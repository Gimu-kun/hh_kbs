"""Đăng ký toàn bộ API cho CRUD và suy diễn."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query

from app.core.audit import audit_reference
from app.services.auth import login, user_for_token
from app.services.errors import KnowledgeError
from app.services.inference import InferenceEngine
from app.services.knowledge_base import KnowledgeBase

router = APIRouter(prefix="/api/v1")
_knowledge: KnowledgeBase | None = None
_engine: InferenceEngine | None = None


def bind(knowledge: KnowledgeBase) -> None:
    global _knowledge, _engine
    _knowledge = knowledge
    _engine = InferenceEngine(knowledge)


def kb() -> KnowledgeBase:
    if _knowledge is None:
        raise HTTPException(500, "Cơ sở tri thức chưa được nạp.")
    return _knowledge


def engine() -> InferenceEngine:
    if _engine is None:
        raise HTTPException(500, "Bộ suy diễn chưa được nạp.")
    return _engine


def _run(action):
    try:
        return action()
    except KnowledgeError as error:
        raise HTTPException(error.status, error.message) from error


@router.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@router.get("/meta", tags=["meta"])
def meta():
    return kb().summary()


def _filter_items(items, collection_name, q, substance, reaction_type, condition, compound_class, problem):
    if q:
        needle = q.lower()
        items = [item for item in items if needle in str(item).lower()]
    if substance and collection_name == "reactions":
        items = [item for item in items if substance in item["reactants"] or substance in item["products"]]
    if reaction_type and collection_name == "reactions":
        items = [item for item in items if item.get("type") == reaction_type]
    if condition and collection_name == "reactions":
        items = [item for item in items if item.get("condition") == condition]
    if compound_class and collection_name == "compounds":
        items = [
            item
            for item in items
            if item.get("class") == compound_class or compound_class in (item.get("ontology") or [])
        ]
    if problem and collection_name == "templates":
        items = [item for item in items if item.get("problem") == problem]
    return items


def _register(prefix, collection_name, create_name, update_name, delete_name) -> None:
    sub = APIRouter(prefix=f"/{prefix}", tags=[prefix])

    def list_items(
        q: str | None = None,
        substance: str | None = None,
        reaction_type: str | None = Query(None, alias="type"),
        condition: str | None = None,
        compound_class: str | None = Query(None, alias="class"),
        problem: str | None = None,
    ):
        items = getattr(kb(), collection_name).list()
        items = _filter_items(items, collection_name, q, substance, reaction_type, condition, compound_class, problem)
        return {"count": len(items), "items": items}

    def get_item(item_id: str):
        item = getattr(kb(), collection_name).get(item_id)
        if item is None:
            raise HTTPException(404, f"Không tìm thấy '{item_id}'.")
        return item

    def create_item(payload: dict):
        return _run(lambda: getattr(kb(), create_name)(payload))

    def update_item(item_id: str, payload: dict):
        return _run(lambda: getattr(kb(), update_name)(item_id, payload))

    def delete_item(item_id: str):
        return _run(lambda: getattr(kb(), delete_name)(item_id))

    sub.add_api_route("", list_items, methods=["GET"], operation_id=f"list_{prefix}")
    sub.add_api_route("", create_item, methods=["POST"], status_code=201, operation_id=f"create_{prefix}")
    sub.add_api_route("/{item_id:path}", get_item, methods=["GET"], operation_id=f"get_{prefix}")
    sub.add_api_route("/{item_id:path}", update_item, methods=["PUT"], operation_id=f"update_{prefix}")
    sub.add_api_route("/{item_id:path}", delete_item, methods=["DELETE"], operation_id=f"delete_{prefix}")
    router.include_router(sub)


for _spec in (
    ("elements", "elements", "create_element", "update_element", "delete_element"),
    ("compounds", "compounds", "create_compound", "update_compound", "delete_compound"),
    ("reactions", "reactions", "create_reaction", "update_reaction", "delete_reaction"),
    ("rules", "rules", "create_rule", "update_rule", "delete_rule"),
    ("conditions", "conditions", "create_condition", "update_condition", "delete_condition"),
    ("heuristics", "heuristics", "create_heuristic", "update_heuristic", "delete_heuristic"),
    ("formulas", "formulas", "create_formula", "update_formula", "delete_formula"),
    ("reagents", "reagents", "create_reagent", "update_reagent", "delete_reagent"),
    ("templates", "templates", "create_template", "update_template", "delete_template"),
):
    _register(*_spec)


@router.post("/solve/balance", tags=["solve"], operation_id="solve_balance")
def solve_balance(payload: dict):
    """Cân bằng và rút gọn phương trình, kèm diễn giải từng bước.

    Body mẫu: {"equation": "Al + O2 → Al2O3"}
    """
    return _run(lambda: engine().balance(str(payload.get("equation") or "")))


@router.post("/solve/chain", tags=["solve"], operation_id="solve_chain")
def solve_chain(payload: dict):
    """Tìm chuỗi phản ứng từ chất xuất phát tới chất đích.

    Body mẫu: {"start": "CaCO3", "target": "CaCl2", "max_steps": 6}
    """
    return _run(
        lambda: engine().chain(
            str(payload.get("start") or ""),
            str(payload.get("target") or ""),
            int(payload.get("max_steps") or 6),
        )
    )


@router.post("/solve/quantity", tags=["solve"], operation_id="solve_quantity")
def solve_quantity(payload: dict):
    """Tính khối lượng, thể tích đktc hoặc số mol theo phương trình.

    kind nhận mass, volume hoặc mole.
    Body mẫu:
    {
      "equation": "Zn + HCl → ZnCl2 + H2",
      "known": {"formula": "Zn", "kind": "mass", "value": 13},
      "find": {"formula": "ZnCl2", "kind": "mass"}
    }
    """
    return _run(lambda: engine().quantity(payload))


def _admin(authorization: str | None = Header(None)) -> str:
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    username = user_for_token(token)
    if username is None:
        raise HTTPException(401, "Cần đăng nhập admin.")
    return username


@router.post("/auth/login", tags=["admin"], operation_id="admin_login")
def admin_login(payload: dict):
    """Đăng nhập admin. Body: {"username": "admin", "password": "hh-admin"}."""
    return _run(lambda: login(str(payload.get("username") or ""), str(payload.get("password") or "")))


@router.get("/admin/reviews", tags=["admin"], operation_id="list_reviews")
def list_reviews(status: str | None = None, authorization: str | None = Header(None)):
    """Danh sách phản ứng chờ duyệt. status: pending, approved hoặc rejected."""
    _admin(authorization)
    items = engine().reviews.list(status)
    return {"count": len(items), "items": items}


@router.post("/admin/reviews/sync", tags=["admin"], operation_id="sync_reviews")
def sync_reviews(authorization: str | None = Header(None)):
    """Sinh lại các phản ứng lệch bộ tham chiếu và đưa vào hàng pending."""
    _admin(authorization)
    current = engine()
    report = audit_reference(
        current.reviews.reference_items(),
        current.knowledge.rules.list(),
        current._catalog(),
    )
    added = current.reviews.record_extras(report["extras"], source="audit")
    return {
        "added": added,
        "correct": report["correct"],
        "wrong": report["wrong"],
        "missing": report["missing"],
        "extra": report["extra"],
        "total": report["total"],
        "rate": report["rate"],
    }


@router.post("/admin/reviews/{review_id}/approve", tags=["admin"], operation_id="approve_review")
def approve_review(review_id: str, payload: dict | None = None, authorization: str | None = Header(None)):
    """Duyệt phản ứng. Body: {"note": "..."}."""
    _admin(authorization)
    note = str((payload or {}).get("note") or "")
    return _run(lambda: engine().reviews.approve(review_id, note))


@router.post("/admin/reviews/{review_id}/reject", tags=["admin"], operation_id="reject_review")
def reject_review(review_id: str, payload: dict | None = None, authorization: str | None = Header(None)):
    """Từ chối phản ứng. Body: {"note": "...", "rule_fault": true}.

    rule_fault = true khi từ chối vì luật sinh ra phản ứng sai; rule_id được giữ lại để sửa luật.
    Phản ứng bị từ chối không được bộ suy diễn dùng lại.
    """
    _admin(authorization)
    body = payload or {}
    result = _run(lambda: engine().reviews.reject(review_id, str(body.get("note") or ""), bool(body.get("rule_fault"))))
    engine().invalidate_generation()
    return result
