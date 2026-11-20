"""Errores con el formato común del contrato: {"error": {code, message, fields?, request_id}}."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("brota")


class AppError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        fields: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields
        self.extra = extra

    def cuerpo(self, request_id: str | None) -> dict[str, Any]:
        err: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.fields:
            err["fields"] = self.fields
        if self.extra:
            err.update(self.extra)
        if request_id:
            err["request_id"] = request_id
        return {"error": err}


def no_encontrado(recurso: str = "recurso") -> AppError:
    return AppError(404, "NOT_FOUND", f"No encontramos el {recurso} o no tienes acceso a él.")


def invalido(fields: dict[str, str], message: str = "Revisa los campos enviados") -> AppError:
    return AppError(422, "VALIDATION_ERROR", message, fields)


def prohibido(message: str = "No tienes permiso para esta acción.") -> AppError:
    return AppError(403, "FORBIDDEN", message)


def conflicto_version(esperada: int, actual: int) -> AppError:
    return AppError(
        409,
        "VERSION_CONFLICT",
        "El registro cambió. Revisa su estado antes de continuar.",
        {"version_esperada": f"Se esperaba la versión {actual}; llegó {esperada}"},
    )


def transicion_invalida(message: str) -> AppError:
    return AppError(409, "INVALID_TRANSITION", message)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _campo(loc: tuple[Any, ...]) -> str:
    partes = [str(p) for p in loc if p not in ("body", "query", "path", "header")]
    return ".".join(partes) or "cuerpo"


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(exc.cuerpo(_request_id(request)), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
        errores = exc.errors()
        if any(e.get("type") == "json_invalid" for e in errores):
            err = AppError(400, "BAD_REQUEST", "El cuerpo no es JSON válido.")
            return JSONResponse(err.cuerpo(_request_id(request)), status_code=400)
        fields: dict[str, str] = {}
        for e in errores:
            fields.setdefault(_campo(tuple(e.get("loc", ()))), e.get("msg", "Valor inválido"))
        en_query = all(e.get("loc", ("",))[0] in ("query", "path", "header") for e in errores)
        status = 400 if en_query else 422
        code = "BAD_REQUEST" if en_query else "VALIDATION_ERROR"
        err = AppError(status, code, "Revisa los campos enviados", fields)
        return JSONResponse(err.cuerpo(_request_id(request)), status_code=status)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 401: "UNAUTHORIZED", 403: "FORBIDDEN"}
        err = AppError(exc.status_code, codes.get(exc.status_code, "HTTP_ERROR"), str(exc.detail))
        return JSONResponse(err.cuerpo(_request_id(request)), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Error no controlado", exc_info=exc)
        err = AppError(500, "INTERNAL_ERROR", "Ocurrió un error inesperado. Intenta de nuevo.")
        return JSONResponse(err.cuerpo(_request_id(request)), status_code=500)
