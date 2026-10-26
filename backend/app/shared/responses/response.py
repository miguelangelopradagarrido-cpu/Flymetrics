from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import Any, Optional

def success_response(message: str, data: Any = None, status_code: int = 200) -> JSONResponse:
    content = {
        "success": True,
        "message": message,
        "data": data if data is not None else {}
    }
    return JSONResponse(content=jsonable_encoder(content), status_code=status_code)

def error_response(message: str, errors: Optional[list] = None, status_code: int = 400) -> JSONResponse:
    content = {
        "success": False,
        "message": message,
        "errors": errors or []
    }
    return JSONResponse(content=jsonable_encoder(content), status_code=status_code)
