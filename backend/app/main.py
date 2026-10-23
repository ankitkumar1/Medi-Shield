from fastapi import FastAPI

from app.config import settings

app = FastAPI(
    title="Medi-Shield",
    description="Multi-agent document intake for MediShield claims.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
