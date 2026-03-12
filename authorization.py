from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timedelta, timezone
from fastapi import Request, HTTPException, Depends, WebSocket, status
from fastapi.security import APIKeyCookie, APIKeyHeader, APIKeyQuery
from beartype import beartype
import jwt

from utils.db.users import (
    get_user_by_id
)
from settings import settings

cookie_scheme = APIKeyCookie(name="token", auto_error=False)
header_scheme = APIKeyHeader(name="Authorization", auto_error=False)
query_scheme = APIKeyQuery(name="token", auto_error=False)

@beartype
def _verify_token(token: str) -> Optional[Dict[str, Any]]:
    if token == settings.get("MASTER_TOKEN"):
        return {"user_id": "master", "nickname": "Master User", "master": True}

    try:
        payload: Dict[str, Any] = jwt.decode(
            token, 
            settings.get("SECRET_KEY"), 
            algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

@beartype
async def is_logged(request: Request, field: str = "headers", raise_on: bool = False) -> Tuple[bool, dict]:
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
                token = request.query_params.get("token")
            case "json":
                data = await request.json()
                token = data.get("token")
            case "data":
                data = await request.form()
                token = data.get("token")
    except:
        if raise_on:
            raise HTTPException(status_code=400, detail="Invalid request format")
        return (False, {})
    
    if token:
        token = token.strip()
    
    if not token:
        if raise_on:
            raise HTTPException(status_code=401, detail="Authentication token missing")
        return (False, {})
    
    payload = _verify_token(token)
    
    if not payload:
        if raise_on:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return (False, {})
    
    if not payload.get("master"):
        user = get_user_by_id(payload.get("user_id"))
        
        if not user:
            if raise_on:
                raise HTTPException(status_code=401, detail="User not found")
            return (False, {})
    
    return (True, payload)

async def check_login_headers(
    request: Request, 
    token: str = Depends(header_scheme)
):
    logged, payload = await is_logged(request, "headers", True)
    return payload

async def check_login_cookies(
    request: Request, 
    token: str = Depends(cookie_scheme)
):
    logged, payload = await is_logged(request, "cookies", True)
    return payload

async def check_login_args(
    request: Request, 
    token: str = Depends(query_scheme)
):
    logged, payload = await is_logged(request, "args", True)
    return payload

def login_required(field: str = "headers"):
    if field == "headers":
        return Depends(check_login_headers)
    elif field == "cookies":
        return Depends(check_login_cookies)
    elif field == "args":
        return Depends(check_login_args)
    return Depends(check_login_headers)

async def get_current_user_ws(
    websocket: WebSocket,
    token: Optional[str] = None
):
    if not token:
        token = websocket.query_params.get("token")
    if not token:
        token = websocket.cookies.get("token")
        
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
        
    payload = _verify_token(token)
    if not payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
        
    if not payload.get("master"):
        user = get_user_by_id(payload.get("user_id"))
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None
        
    return payload

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
    return jwt.encode(payload, settings.get("SECRET_KEY"), algorithm="HS256")