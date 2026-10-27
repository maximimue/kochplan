from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.errors import AppError, app_error_handler
from app.routers import auth, me, meta, plans, recipes

settings = get_settings()

app = FastAPI(
    title="Kochplan API",
    version="0.1.0",
    docs_url="/docs" if settings.env == "dev" else None,
    redoc_url=None,
)
app.add_exception_handler(AppError, app_error_handler)
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
        allow_methods=["*"], allow_headers=["Authorization", "Content-Type", "Accept-Language"],
    )

for r in (auth.router, me.router, meta.router, recipes.router, plans.router):
    app.include_router(r, prefix="/v1")


@app.get("/healthz", include_in_schema=False)
async def healthz():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok"}
