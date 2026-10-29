from fastapi import Request, FastAPI
from fastapi.exceptions import RequestValidationError
from app.shared.exceptions.exceptions import AppException
from app.shared.responses.response import error_response

def _add_cors_headers(resp, request: Request):
    origin = request.headers.get("origin")
    if origin:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Access-Control-Allow-Methods"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "*"
        resp.headers["Vary"] = "Origin"
    return resp

def setup_error_handlers(app: FastAPI):
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        """Maneja las excepciones personalizadas del dominio/aplicación."""
        resp = error_response(
            message=exc.message,
            errors=exc.errors,
            status_code=exc.status_code
        )
        return _add_cors_headers(resp, request)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Maneja los errores de validación de esquemas (Pydantic v2)."""
        errors = []
        for error in exc.errors():
            loc = " -> ".join(map(str, error["loc"]))
            msg = error["msg"]
            errors.append(f"{loc}: {msg}")
            
        resp = error_response(
            message="Error de validación en los datos enviados",
            errors=errors,
            status_code=400
        )
        return _add_cors_headers(resp, request)

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Maneja cualquier error de servidor inesperado sin fugar detalles internos."""
        import logging
        logging.getLogger("uvicorn.error").error(f"Internal Server Error: {str(exc)}", exc_info=True)
        resp = error_response(
            message="Ocurrió un error inesperado en el servidor",
            errors=["Error interno procesando la solicitud. Si el problema persiste, contacte a soporte."],
            status_code=500
        )
        return _add_cors_headers(resp, request)
