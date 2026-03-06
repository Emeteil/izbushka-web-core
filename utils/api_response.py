from flask import jsonify, Response
from settings import * 

def apiResponse(data, code: int = 200, errorMessage: str = "Error") -> Response:
    if not (400 <= code <= 500):
        return (
            jsonify({"status": "success", "data": data}),
            code,
        )
    else:
        return jsonify(
            {
                "status": "error",
                "error": {
                    "code": code,
                    "message": errorMessage,
                    "details": data,
                },
            }
        ), code


class ApiError(Exception):
    def __init__(self, code=500, data=None):
        self.code = code
        self.data = data
        
    def __str__(self):
        return self.data