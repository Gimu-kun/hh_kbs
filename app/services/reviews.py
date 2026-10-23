"""Hàng kiểm duyệt phản ứng do luật sinh ra và không có trong bộ tham chiếu.

Bộ sinh sản phẩm không đọc file này và không đọc reactions.json.
Chỉ lớp kiểm duyệt mở tests/fixtures/reference_reactions.json để biết
một phản ứng đã có trong bộ tham chiếu hay chưa.
"""

from __future__ import annotations

import fcntl
import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.forward import reaction_signature
from app.services.errors import KnowledgeError

FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "reference_reactions.json"


def _load_items(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("items") or [])


class ReviewStore:
    def __init__(self, data_dir: Path, reference_path: Path | None = None):
        self.path = Path(data_dir) / "reaction_reviews.json"
        self.reference_path = reference_path or FIXTURE
        self.items: list[dict] = _load_items(self.path)
        self.by_id = {item["id"]: item for item in self.items}
        self.by_sig: dict[tuple, dict] = {}
        for item in self.items:
            self.by_sig[self._signature(item)] = item
        self.reference = self._load_reference()

    def _load_reference(self) -> set[tuple]:
        found = set()
        for item in _load_items(self.reference_path):
            found.add(reaction_signature(item["reactants"], item["products"], item.get("condition") or "NONE"))
        return found

    @staticmethod
    def _signature(item: dict) -> tuple:
        return reaction_signature(item["reactants"], item["products"], item.get("condition") or "NONE")

    def status_of(self, reactants: list[str], products: list[str], condition: str) -> str:
        signature = reaction_signature(reactants, products, condition)
        record = self.by_sig.get(signature)
        if record and record["status"] in {"approved", "rejected"}:
            return record["status"]
        if signature in self.reference:
            return "referenced"
        if record:
            return record["status"]
        return "unknown"

    def reference_items(self) -> list[dict]:
        return _load_items(self.reference_path)

    def rejected_signatures(self) -> set[tuple]:
        return {signature for signature, item in self.by_sig.items() if item["status"] == "rejected"}

    def classify_step(self, reaction: dict, source: str = "solution") -> dict:
        """Gắn trạng thái cho một bước lời giải. Phản ứng lạ được ghi pending."""
        signature = reaction_signature(reaction["reactants"], reaction["products"], reaction.get("condition") or "NONE")
        record = self.by_sig.get(signature)
        if record and record["status"] == "rejected":
            return record
        if signature in self.reference:
            return {"status": "referenced", "id": record["id"] if record else None}
        if record:
            return record
        return self._append(reaction, "pending", source)

    def record_extras(self, reactions: list[dict], source: str = "audit") -> int:
        added = 0
        for reaction in reactions:
            signature = reaction_signature(
                reaction["reactants"], reaction["products"], reaction.get("condition") or "NONE"
            )
            if signature in self.reference or signature in self.by_sig:
                continue
            self._append(reaction, "pending", source, save=False)
            added += 1
        if added:
            self._save()
        return added

    def list(self, status: str | None = None) -> list[dict]:
        if not status:
            return list(self.items)
        return [item for item in self.items if item["status"] == status]

    def get(self, review_id: str) -> dict:
        item = self.by_id.get(review_id)
        if item is None:
            raise KnowledgeError(f"Không tìm thấy bản ghi kiểm duyệt {review_id}.", 404)
        return item

    def approve(self, review_id: str, note: str) -> dict:
        return self._decide(review_id, "approved", note, False)

    def reject(self, review_id: str, note: str, rule_fault: bool) -> dict:
        return self._decide(review_id, "rejected", note, rule_fault)

    def reopen(self, review_id: str, note: str) -> dict:
        item = self.get(review_id)
        if item["status"] != "rejected":
            raise KnowledgeError("Chỉ mở lại được phản ứng đang ở trạng thái từ chối.")
        self._remember(item, "reopen", note)
        item["status"] = "pending"
        item["note"] = str(note or "").strip()
        self._save()
        return item

    def _decide(self, review_id: str, status: str, note: str, rule_fault: bool) -> dict:
        item = self.get(review_id)
        if item["status"] == "rejected":
            raise KnowledgeError("Phản ứng đã bị từ chối chỉ được mở lại bằng thao tác reopen.")
        item["status"] = status
        item["note"] = str(note or "").strip()
        if status == "rejected":
            item["rule_fault"] = bool(rule_fault)
        self._remember(item, status, note)
        self._save()
        return item

    @staticmethod
    def _remember(item: dict, action: str, note: str) -> None:
        history = item.setdefault("history", [])
        history.append(
            {
                "action": action,
                "note": str(note or "").strip(),
                "rule_fault": bool(item.get("rule_fault")),
                "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )

    def _append(self, reaction: dict, status: str, source: str, save: bool = True) -> dict:
        review_id = f"RV{len(self.items) + 1:05d}"
        item = {
            "id": review_id,
            "status": status,
            "condition": reaction.get("condition") or "NONE",
            "reactants": list(reaction["reactants"]),
            "products": list(reaction["products"]),
            "coefficients": list(reaction.get("coefficients") or []),
            "rule_id": reaction.get("rule_id"),
            "rule_text": reaction.get("rule_text") or "",
            "source": source,
            "note": "",
            "rule_fault": False,
        }
        self.items.append(item)
        self.by_id[review_id] = item
        self.by_sig[self._signature(item)] = item
        if save:
            self._save()
        return item

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"items": self.items}, ensure_ascii=False, indent=2)
        with self.path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                handle.seek(0)
                handle.truncate()
                handle.write(payload)
                handle.flush()
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
