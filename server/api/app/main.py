from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
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


def _denullify(node: object) -> object:
    if isinstance(node, dict):
        node = {k: _denullify(v) for k, v in node.items()}
        any_of = node.get("anyOf")
        if isinstance(any_of, list) and len(any_of) == 2:
            null_members = [m for m in any_of if m == {"type": "null"}]
            other_members = [m for m in any_of if m != {"type": "null"}]
            if len(null_members) == 1 and len(other_members) == 1:
                del node["anyOf"]
                node.update(other_members[0])
                node["nullable"] = True
        return node
    if isinstance(node, list):
        return [_denullify(v) for v in node]
    return node


def _custom_openapi() -> dict:
    # ponytail: swift-openapi-generator 1.14.3 verwirft OpenAPI-3.1-Nullable (anyOf mit null)
    # komplett statt sie als optional zu erzeugen, siehe apple/swift-openapi-generator. Daher
    # hier direkt als OpenAPI-3.0-Stil (nullable: true) ausliefern statt im Client nachzubessern.
    if app.openapi_schema is None:
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        schema = _denullify(schema)
        schema["openapi"] = "3.0.3"
        app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _custom_openapi
