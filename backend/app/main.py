from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.cases import router as cases_router
from app.config import settings
from app.db import init_db
from app.pipeline.groq_vision import groq_enabled


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Medi-Shield",
    description="Multi-agent document intake for MediShield claims.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(cases_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "env": settings.app_env,
        "classifier": "groq" if groq_enabled() else "local",
    }
