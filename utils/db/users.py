from typing import Dict, List, Optional, Union, Iterable
from cachetools import cached, TTLCache
from beartype import beartype
from settings import settings
from threading import Lock
import shortuuid
import json, os
import time

from utils.db.cache_manager import users_cache, clear_cache

lock = Lock()

if not os.path.isfile(settings["users_json_path"]):
    os.makedirs(os.path.dirname(settings["users_json_path"]), exist_ok=True)
    with open(settings["users_json_path"], "w", encoding="utf-8") as f:
        f.write("{}")

def _generate_user_id() -> str:
    return f"user_{shortuuid.uuid()}"

@beartype
def _load_users() -> Dict[str, Dict[str, Union[str, List[str]]]]:
    with lock:
        try:
            with open(settings["users_json_path"], "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

@beartype
def _save_users(data: Dict[str, Dict[str, Union[str, List[str]]]]) -> None:
    with lock:
        with open(settings["users_json_path"], "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        clear_cache()

@cached(users_cache["get_users"])
@beartype
def get_users() -> Dict[str, Dict[str, Union[str, List[str]]]]:
    return _load_users()

@beartype
def update_users(data: Dict[str, Dict[str, Union[str, List[str]]]]) -> None:
    _save_users(data)

@cached(users_cache["_get_user_by_id"])
@beartype
def _get_user_by_id(user_id: str) -> Optional[Dict[str, Union[str, List[str]]]]:
    users = get_users()
    return users.get(user_id)

@beartype
def get_user_by_id(
    user_id: str,
    keys: Optional[Iterable[str]] = None
) -> Optional[Dict[str, Union[str, List[str]]]]:
    user = _get_user_by_id(user_id)
    
    if not user:
        return None
    
    if not keys:
        return user
    
    data = {}
    for key in keys:
        data[key] = user[key]
    
    return data

@cached(users_cache["_get_user_by_nickname"])
@beartype
def _get_user_by_nickname(nickname: str) -> Optional[Dict[str, Union[str, List[str]]]]:
    users = get_users()
    return next(
        (user for user in users.values() if user["nickname"] == nickname),
        None
    )

@beartype
def get_user_by_nickname(
    nickname: str,
    keys: Optional[Iterable[str]] = None
) -> Optional[Dict[str, Union[str, List[str]]]]:
    user = _get_user_by_nickname(nickname)
    
    if not user:
        return None
    
    if not keys:
        return user
    
    data = {}
    for key in keys:
        data[key] = user[key]
    
    return data

@beartype
def create_user(
    nickname: str,
    password_hash: str,
) -> str:
    users = get_users()
    user_id = _generate_user_id()
    
    users[user_id] = {
        "id": user_id,
        "nickname": nickname,
        "password_hash": password_hash,
        "time_registration": time.time(),
    }
    _save_users(users)
    
    return user_id

@beartype
def delete_user(user_id: str):
    users = get_users()
    
    del users[user_id]
    
    _save_users(users)

@beartype
def update_user(
    user_id: str,
    nickname: Optional[str] = None,
    password_hash: Optional[str] = None,
    email: Optional[str] = None,
    full_name: Optional[str] = None
) -> None:
    users = get_users()
    if user_id not in users:
        raise ValueError("User not found")
    
    if nickname is not None:
        users[user_id]["nickname"] = nickname
    if password_hash is not None:
        users[user_id]["password_hash"] = password_hash
    if email is not None:
        users[user_id]["email"] = email
    if full_name is not None:
        users[user_id]["full_name"] = full_name
    
    _save_users(users)