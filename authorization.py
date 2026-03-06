from typing import Any, Callable, Dict, Optional, TypeVar, Tuple
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request
from beartype import beartype
import jwt

from utils.api_response import ApiError
from utils.db.users import (
    get_user_by_id
)
from settings import *

@beartype
def _verify_token(token: str) -> Optional[Dict[str, Any]]:
    if token == app.config["MASTER_TOKEN"]:
        return {"user_id": "master", "nickname": "Master User", "master": True}
    
    try:
        payload: Dict[str, Any] = jwt.decode(
            token, 
            app.config["SECRET_KEY"], 
            algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

@beartype
def is_logged(field: str = "headers", raise_on: bool = False) -> Tuple[bool, dict]:
    token: Optional[str] = None
    
    try:
        match field:
            case "headers":
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer"):
                    parts = auth_header.split()
                    if len(parts) == 2:
                        token = parts[1]
            case "cookies":
                token = request.cookies.get("token")
            case "args":
                token = request.args.get("token")
            case "json":
                token = request.get_json().get("token")
            case "data":
                token = request.get_data().get("token")
    except:
        if raise_on:
            raise ApiError(400)
        return (False, {})
    
    if token:
        token = token.strip()
    
    if not token:
        if raise_on:
            raise ApiError(401)
        return (False, {})
    
    payload = _verify_token(token)
    
    if not payload:
        if raise_on:
            raise ApiError(401)
        return (False, {})
    
    if not payload.get("master"):
        user = get_user_by_id(payload.get("user_id"))
        
        if not user:
            if raise_on:
                raise ApiError(401)
            return (False, {})
    
    return (True, payload)

F = TypeVar('F', bound=Callable[..., Any])
@beartype
def login_required(field: str = "headers") -> Callable[[F], F]:
    def decorator(f: F) -> F:
        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            _, payload = is_logged(field, True)
            kwargs['payload'] = payload
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

@beartype
def generate_token(
        user_id: str, 
        nickname: str, 
        TTL: timedelta = timedelta(days=1)
    ) -> str:
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "nickname": nickname,
        "exp": datetime.now(timezone.utc) + TTL
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")