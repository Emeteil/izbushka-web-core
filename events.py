from fastapi import Request, HTTPException
from fastapi.responses import FileResponse
from utils.api_response import apiResponse, ApiError
from utils.status_codes import status_codes
from traceback import extract_tb, format_exc
from starlette.exceptions import HTTPException as StarletteHTTPException
from settings import app, settings, templates
import os

@app.get("/favicon", include_in_schema=False)
@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.png", include_in_schema=False)
async def favicon():
    return FileResponse("static/images/favicon.png")

@app.exception_handler(StarletteHTTPException)
@app.exception_handler(Exception)
@app.exception_handler(HTTPException)
@app.exception_handler(ApiError)
async def handle_error(request: Request, error: Exception):
    status_code = getattr(error, 'status_code', getattr(error, 'code', 500))
    data = getattr(error, 'data', getattr(error, 'detail', None))
    
    status_code_data = status_codes.get(status_code, {}).copy()
    
    if not status_code_data:
        status_code_data = {
            "title": f"{status_code} Error",
            "description": "Unknown error"
        }
    
    if data and isinstance(data, str) and data != "Unauthorized" and not data.startswith("4"):
        status_code_data["description"] = data
    elif data and not isinstance(data, str):
        status_code_data["description"] = data
    
    if settings.get("debug") and (500 <= status_code <= 599): 
        print(format_exc())
    
    if request.url.path.startswith('/api'):
        if settings.get("debug") and (500 <= status_code <= 599) and hasattr(error, '__traceback__') and error.__traceback__:
            lf = extract_tb(error.__traceback__)[-1]
            content = {
                "short_message": str(error),
                "type": type(error).__name__,
                "filename": os.path.basename(lf.filename),
                "function_name": lf.name,
                "code_line": lf.line.replace('"', "'") if lf.line else "",
                "line_number": lf.lineno
            }
        else:
            content = status_code_data["title"]

        return apiResponse(
            content,
            status_code,
            status_code_data["description"]
        )
    else:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "status_code": status_code,
                "data": status_code_data
            },
            status_code=status_code
        )