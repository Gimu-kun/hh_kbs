"""Ứng dụng FastAPI của cơ sở tri thức hóa vô cơ."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import bind
from app.api import router as api_router
from app.core.config import data_dir
from app.services.errors import KnowledgeError
from app.services.knowledge_base import KnowledgeBase


@asynccontextmanager
async def lifespan(_app: FastAPI):
    bind(KnowledgeBase(data_dir()))
    yield


app = FastAPI(
    title="Cơ sở tri thức hóa vô cơ THPT",
    description=(
        "Mô hình K = (E, C, R, L, Cond, H) kèm công thức tính, kho thuốc thử và template diễn giải. "
        "CRUD từng thành phần và API suy diễn cân bằng, chuỗi phản ứng, bài toán đại lượng."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(KnowledgeError)
def knowledge_error_handler(_request, exc: KnowledgeError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message})


app.include_router(api_router)

