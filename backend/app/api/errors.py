"""The error envelope from docs/api-contract.md "Conventions":
{"error": {"code": "...", "message": "..."}} — a stable machine-readable
`code`, not just an HTTP status, so the frontend can branch on *why* a
request failed and show a precise message (ties to product-scope.md §0:
a vague error is a UX cost).
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

_STATUS_TO_CODE = {
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    422: "invalid_input",
}


class APIError(Exception):
    """Raise this for any business-rule failure that needs a specific `code`."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        code = _STATUS_TO_CODE.get(exc.status_code, "error")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": str(exc.detail)}},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "invalid_input", "message": str(exc.errors())}},
        )
