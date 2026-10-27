from fastapi import Request
from fastapi.responses import JSONResponse

from app.i18n import resolve_locale, t


class AppError(Exception):
    def __init__(self, code: str, status: int = 400, **params):
        self.code, self.status, self.params = code, status, params


class Warning_:
    """Hinweis im Ergebnis (kein Fehler). Wird beim Serialisieren lokalisiert."""

    def __init__(self, code: str, **params):
        self.code, self.params = code, params

    def render(self, locale: str) -> dict:
        return {"code": self.code, "message": t(f"warnings.{self.code}", locale, **self.params)}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    locale = resolve_locale(request.headers.get("accept-language"))
    body = {"error": {"code": exc.code, "message": t(f"errors.{exc.code}", locale, **exc.params)}}
    if "detail" in exc.params:
        body["error"]["detail"] = exc.params["detail"]
    return JSONResponse(body, status_code=exc.status)
