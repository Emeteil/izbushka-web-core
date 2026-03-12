from fastapi.responses import JSONResponse
from settings import * 

def apiResponse(data, code: int = 200, errorMessage: str = "Error") -> JSONResponse:
    if not (400 <= code <= 599):
        return JSONResponse(
            content={"status": "success", "data": data},
            status_code=code
        )
    else:
        return JSONResponse(
            content={
                "status": "error",
                "error": {
                    "code": code,
                    "message": errorMessage,
                    "details": data,
                },
            },
            status_code=code
        )


class ApiError(Exception):
    def __init__(self, code=500, data=None):
        self.code = code
        self.data = data
        
    def __str__(self):
        return str(self.data)