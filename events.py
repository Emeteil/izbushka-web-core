from flask import request, render_template, send_file
from utils.api_response import *
from utils.status_codes import status_codes
from traceback import extract_tb, format_exc
from settings import *
import os

@app.route("/favicon")
@app.route("/favicon.ico")
@app.route("/favicon.png")
def favicon():
    return send_file("static/images/favicon.png")

@app.errorhandler(Exception)
def handle_error(error):
    status_code = getattr(error, "code", 500)
    data = getattr(error, "data", None)
    status_code_data = status_codes[status_code].copy() if status_code in status_codes else None
    
    if not status_code_data:
        status_code_data = {
            "title": f"{status_code} Error",
            "description": "Unknown error"
        }
    if data: status_code_data["description"] = data
    
    if settings["debug"] and (500 <= status_code <= 599): print(format_exc())
    if request.path.startswith("/api"):
        lf = extract_tb(error.__traceback__)[-1]
        return apiResponse(
            {
                "short_message": str(error),
                "type": type(error).__name__,
                "filename": os.path.basename(lf.filename),
                "function_name": lf.name,
                "code_line": lf.line.replace('"', "'"),
                "line_number": lf.lineno
            } if settings["debug"] and (500 <= status_code <= 599) else status_code_data["title"],
            status_code,
            status_code_data["description"]
        )
    else:
        return render_template(
            "error.html",
            status_code=status_code,
            data=status_code_data
        ), status_code