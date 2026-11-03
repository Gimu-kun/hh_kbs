"""API CRUD cho cơ sở tri thức và API giải ba dạng bài.

Chạy: uvicorn cstt.api:app --reload
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from cstt.infer import solve
from cstt.store import (
    StoreError,
    add_named,
    concept_file,
    create_record,
    create_special_class,
    delete_named,
    delete_record,
    delete_special_class,
    get_max_depth,
    get_record,
    list_named,
    list_records,
    list_special_classes,
    replace_record,
    replace_special_class,
    rules_file,
    set_max_depth,
)

app = FastAPI(title="Cơ sở tri thức hoá vô cơ THCS", version="1.0")


class Element(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str
    name: str
    z: int
    period: int
    group: int | None
    block: str
    series: str | None
    mass: float
    valence: list[int]
    type: str
    type_label: str
    activity: int | None
    groups: list[str]


class Composition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    element: str
    quantity: int


class Compound(BaseModel):
    model_config = ConfigDict(extra="forbid")
    formula: str
    name: str
    class_: str = Field(alias="class")
    class_label: str
    composition: list[Composition]
    state: str
    state_label: str


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    name: str
    symbol: str
    complexity: int
    description: str


class ClassNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    children: list[str]


class SpecialClass(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    formula: str
    class_: str = Field(alias="class")


class FormulaName(BaseModel):
    model_config = ConfigDict(extra="forbid")
    formula: str


class Anion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    formula: str
    charge: int
    composition: list[Composition]


class When(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cation: str | None
    cation_in: list[str]
    anion: str | None
    anion_in: list[str]


class Solubility(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    when: When
    result: str


class ConditionBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    formula: str
    conditions: list[str]


class ReactionRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: str
    name: str
    classes: list[str] = []
    groups: list[str] = []
    conditions: list[str] = []
    conditions_for: list[ConditionBinding] = []
    solubility: list[str] = []
    exclude_compounds: list[str] = []
    exclude_metals: list[str] = []
    exclude_acids: list[str] = []
    exclude_anions: list[str] = []
    exclude_cations: list[str] = []
    exclude_solubility: list[str] = []
    reagent: str | None = None
    gas: str | None = None


class Depth(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_depth: int = Field(ge=1)


class Constant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    symbol: str
    value: float
    unit: str


class Expr(BaseModel):
    model_config = ConfigDict(extra="forbid")
    var: str | None = None
    op: str | None = None
    args: list["Expr"] = []
    left: "Expr | None" = None
    right: "Expr | None" = None


class Equation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    left: Expr
    right: Expr


class Formula(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    variables: list[str]
    applies_when: str | None
    equation: Equation
    units: dict[str, str | None]


class Known(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chat: str
    dai_luong: str
    gia_tri: float


class Goal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chat: str
    dai_luong: str


class Problem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    loai: int
    phan_ung: str | None = None
    chat_dau: str | None = None
    chat_dich: str | None = None
    che_do: str | None = None
    chat_cho_phep: list[str] | None = None
    chat_tham_gia: list[str] | None = None
    biet: list[Known] | None = None
    tim: Goal | None = None


class BalanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phan_ung: str


class ChainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chat_dau: str
    chat_dich: str
    che_do: str = "tat_ca"
    chat_cho_phep: list[str] | None = None


class CalcRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phan_ung: str | None = None
    chat_tham_gia: list[str] | None = None
    biet: list[Known]
    tim: Goal


Expr.model_rebuild()


def _dump(model: BaseModel) -> dict:
    return model.model_dump(mode="json", by_alias=True)


def _call(action):
    try:
        return action()
    except StoreError as error:
        raise HTTPException(error.status, error.message) from error


def _mount(path: str, file_of, collection: str, identity: str, model: type[BaseModel]) -> None:
    def listing():
        return _call(lambda: list_records(file_of(), collection))

    def creating(body: model):
        return _call(lambda: create_record(file_of(), collection, identity, _dump(body)))

    def reading(item_id: str):
        return _call(lambda: get_record(file_of(), collection, identity, item_id))

    def replacing(item_id: str, body: model):
        return _call(lambda: replace_record(file_of(), collection, identity, item_id, _dump(body)))

    def removing(item_id: str):
        _call(lambda: delete_record(file_of(), collection, identity, item_id))

    listing.__name__ = f"list_{collection}_{path.strip('/').replace('/', '_')}"
    creating.__name__ = f"create_{collection}_{path.strip('/').replace('/', '_')}"
    reading.__name__ = f"read_{collection}_{path.strip('/').replace('/', '_')}"
    replacing.__name__ = f"replace_{collection}_{path.strip('/').replace('/', '_')}"
    removing.__name__ = f"delete_{collection}_{path.strip('/').replace('/', '_')}"
    app.get(path)(listing)
    app.post(path, status_code=201)(creating)
    app.get(path + "/{item_id:path}")(reading)
    app.put(path + "/{item_id:path}")(replacing)
    app.delete(path + "/{item_id:path}", status_code=204)(removing)


_mount("/api/nguyen-to", lambda: concept_file("elements.json"), "items", "symbol", Element)
_mount("/api/hop-chat", lambda: concept_file("compounds.json"), "items", "formula", Compound)
_mount("/api/dieu-kien", lambda: concept_file("conditions.json"), "items", "code", Condition)
_mount("/api/lop", lambda: rules_file("constraints.json"), "classes", "id", ClassNode)
_mount("/api/anion", lambda: rules_file("constraints.json"), "anions", "formula", Anion)
_mount("/api/do-tan", lambda: rules_file("constraints.json"), "solubility", "id", Solubility)
_mount("/api/hang-so", lambda: rules_file("formulas.json"), "constants", "id", Constant)
_mount("/api/cong-thuc", lambda: rules_file("formulas.json"), "items", "id", Formula)
_mount("/api/luat-phan-ung", lambda: rules_file("reactions.json"), "rules", "id", ReactionRule)


def _mount_names(path: str, collection: str) -> None:
    file_of = lambda: rules_file("constraints.json")

    def listing():
        return _call(lambda: list_named(file_of(), collection))

    def creating(body: FormulaName):
        return _call(lambda: add_named(file_of(), collection, body.formula))

    def removing(item_id: str):
        _call(lambda: delete_named(file_of(), collection, item_id))

    listing.__name__ = f"list_{collection}"
    creating.__name__ = f"create_{collection}"
    removing.__name__ = f"delete_{collection}"
    app.get(path)(listing)
    app.post(path, status_code=201)(creating)
    app.delete(path + "/{item_id:path}", status_code=204)(removing)


_mount_names("/api/oxit-trung-tinh", "neutral_oxides")
_mount_names("/api/anion-muoi-axit", "acid_salt_anions")


@app.get("/api/lop-dac-biet")
def list_special() -> list[dict]:
    return list_special_classes()


@app.post("/api/lop-dac-biet", status_code=201)
def create_special(body: SpecialClass) -> dict:
    return _call(lambda: create_special_class(body.formula, body.class_))


@app.put("/api/lop-dac-biet/{item_id:path}")
def replace_special(item_id: str, body: SpecialClass) -> dict:
    if body.formula != item_id:
        raise HTTPException(422, f"formula trong nội dung phải là {item_id}.")
    return _call(lambda: replace_special_class(item_id, body.class_))


@app.delete("/api/lop-dac-biet/{item_id:path}", status_code=204)
def remove_special(item_id: str) -> None:
    _call(lambda: delete_special_class(item_id))


@app.get("/api/do-sau")
def read_depth() -> dict:
    return get_max_depth()


@app.put("/api/do-sau")
def write_depth(body: Depth) -> dict:
    return _call(lambda: set_max_depth(body.max_depth))


@app.post("/api/giai")
def giai(body: Problem) -> dict:
    return solve(body.model_dump(exclude_none=True))


@app.post("/api/giai/can-bang")
def giai_can_bang(body: BalanceRequest) -> dict:
    return solve({"loai": 1, "phan_ung": body.phan_ung})


@app.post("/api/giai/chuoi")
def giai_chuoi(body: ChainRequest) -> dict:
    problem = {
        "loai": 2,
        "chat_dau": body.chat_dau,
        "chat_dich": body.chat_dich,
        "che_do": body.che_do,
    }
    if body.chat_cho_phep is not None:
        problem["chat_cho_phep"] = body.chat_cho_phep
    return solve(problem)


@app.post("/api/giai/tinh")
def giai_tinh(body: CalcRequest) -> dict:
    problem = {"loai": 3, "biet": [item.model_dump() for item in body.biet], "tim": body.tim.model_dump()}
    if body.phan_ung:
        problem["phan_ung"] = body.phan_ung
    if body.chat_tham_gia is not None:
        problem["chat_tham_gia"] = body.chat_tham_gia
    return solve(problem)
