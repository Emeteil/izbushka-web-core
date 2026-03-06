from utils.api_response import *
from flask import request

from authorization import *
from utils.validation.user_data import (
    validate_register_data,
    NICKNAME_LENGTH,
    PASSWORD_LENGTH
)
from utils.password_hash import *
from utils.db.users import (
    get_user_by_nickname,
    create_user
)
from settings import *

# @app.route("/api/authorization/register", methods=["POST"])
# @limiter.limit("10 per 2 minute")
# def api_register():
#     data = request.get_json()
    
#     nickname: str = data.get("nickname")
#     password: str = data.get("password")

#     errors = validate_register_data(
#         nickname,
#         password
#     )
    
#     if len(errors) != 0:
#         raise ApiError(400, errors)
    
#     if get_user_by_nickname(nickname):
#         raise ApiError(400, ["Nickname already exists"])

#     password_hash = generate_password_hash(password)
    
#     user_id: str = create_user(
#         nickname,
#         password_hash
#     )
    
#     token = generate_token(user_id, nickname)
    
#     response = apiResponse({
#         "message": "User registered successfully",
#         "user_id": user_id,
#         "nickname": nickname,
#         "preferred_redirect": "/"
#     }, 201)
    
#     response[0].set_cookie("token", token, httponly=True, secure=True, samesite="Strict")
    
#     return response

@app.route("/api/authorization/login", methods=["POST"])
@limiter.limit("6 per 3 minute")
def api_login():
    data = request.get_json()
    nickname = data.get("nickname")[:NICKNAME_LENGTH[1]]
    password = data.get("password")[:PASSWORD_LENGTH[1]]

    if not nickname or not password:
        raise ApiError(400, 'Need “nickname” and “password” in data!')

    user = get_user_by_nickname(nickname)
    
    if not user or not check_password_hash(user["password_hash"], password):
        raise ApiError(401, "Invalid nickname or password!")
    
    token: str = generate_token(user["id"], user["nickname"])
    
    response = apiResponse({
        "message": "Login successful",
        "user_id": user["id"],
        "nickname": user["nickname"],
        "preferred_redirect": "/"
    }, 200)
    
    response[0].set_cookie("token", token)
    
    return response

@app.route("/api/authorization/request_api_key", methods=["POST"])
@limiter.limit("5 per 30 minute")
@login_required()
def api_request_api_key(payload):
    token: str = generate_token(payload["user_id"], payload["nickname"])
    
    return apiResponse({
        "token": token
    }, 201)