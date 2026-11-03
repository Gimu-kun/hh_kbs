"""Đọc và ghi các file JSON của cơ sở tri thức, rồi nạp lại máy giải."""

from __future__ import annotations

import json
from pathlib import Path

from cstt import kb as kb_paths
from cstt.chem import ChemError
from cstt.infer import reload_kb


class StoreError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def concept_file(name: str) -> Path:
    return kb_paths.CONCEPT / name


def rules_file(name: str) -> Path:
    return kb_paths.RULES / name


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def commit_json(path: Path, data: dict) -> None:
    from cstt.validate import validate_knowledge

    original = path.read_text(encoding="utf-8")
    _write(path, data)
    try:
        reload_kb()
        validate_knowledge()
    except ChemError as error:
        path.write_text(original, encoding="utf-8")
        reload_kb()
        raise StoreError(422, str(error)) from error


def _write(path: Path, data: dict) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def list_records(path: Path, collection: str) -> list:
    return read_json(path)[collection]


def get_record(path: Path, collection: str, identity: str, value: str) -> dict:
    for item in list_records(path, collection):
        if item[identity] == value:
            return item
    raise StoreError(404, f"Không có {identity} {value}.")


def create_record(path: Path, collection: str, identity: str, record: dict) -> dict:
    data = read_json(path)
    if any(item[identity] == record[identity] for item in data[collection]):
        raise StoreError(409, f"{identity} {record[identity]} đã có.")
    data[collection].append(record)
    commit_json(path, data)
    return record


def replace_record(path: Path, collection: str, identity: str, value: str, record: dict) -> dict:
    if record[identity] != value:
        raise StoreError(422, f"{identity} trong nội dung phải là {value}.")
    data = read_json(path)
    for index, item in enumerate(data[collection]):
        if item[identity] == value:
            data[collection][index] = record
            commit_json(path, data)
            return record
    raise StoreError(404, f"Không có {identity} {value}.")


def delete_record(path: Path, collection: str, identity: str, value: str) -> None:
    data = read_json(path)
    kept = [item for item in data[collection] if item[identity] != value]
    if len(kept) == len(data[collection]):
        raise StoreError(404, f"Không có {identity} {value}.")
    data[collection] = kept
    commit_json(path, data)


def list_named(path: Path, collection: str) -> list[str]:
    return list(read_json(path)[collection])


def add_named(path: Path, collection: str, value: str) -> str:
    data = read_json(path)
    if value in data[collection]:
        raise StoreError(409, f"{value} đã có.")
    data[collection].append(value)
    commit_json(path, data)
    return value


def delete_named(path: Path, collection: str, value: str) -> None:
    data = read_json(path)
    if value not in data[collection]:
        raise StoreError(404, f"Không có {value}.")
    data[collection] = [item for item in data[collection] if item != value]
    commit_json(path, data)


def list_special_classes() -> list[dict]:
    mapping = read_json(rules_file("constraints.json"))["special_class"]
    return [{"formula": formula, "class": class_id} for formula, class_id in mapping.items()]


def create_special_class(formula: str, class_id: str) -> dict:
    path = rules_file("constraints.json")
    data = read_json(path)
    if formula in data["special_class"]:
        raise StoreError(409, f"Công thức {formula} đã có lớp đặc biệt.")
    data["special_class"][formula] = class_id
    commit_json(path, data)
    return {"formula": formula, "class": class_id}


def replace_special_class(formula: str, class_id: str) -> dict:
    path = rules_file("constraints.json")
    data = read_json(path)
    if formula not in data["special_class"]:
        raise StoreError(404, f"Không có lớp đặc biệt cho {formula}.")
    data["special_class"][formula] = class_id
    commit_json(path, data)
    return {"formula": formula, "class": class_id}


def delete_special_class(formula: str) -> None:
    path = rules_file("constraints.json")
    data = read_json(path)
    if formula not in data["special_class"]:
        raise StoreError(404, f"Không có lớp đặc biệt cho {formula}.")
    del data["special_class"][formula]
    commit_json(path, data)


def get_max_depth() -> dict:
    return {"max_depth": read_json(rules_file("reactions.json"))["max_depth"]}


def set_max_depth(value: int) -> dict:
    path = rules_file("reactions.json")
    data = read_json(path)
    data["max_depth"] = value
    commit_json(path, data)
    return {"max_depth": value}
