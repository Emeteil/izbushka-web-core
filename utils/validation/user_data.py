from typing import List, Optional, Tuple
from beartype import beartype
import re

from settings import *

NICKNAME_LENGTH: Tuple[int, int] = tuple(settings["user_data_settings"]["length"]["nickname"])
PASSWORD_LENGTH: Tuple[int, int] = tuple(settings["user_data_settings"]["length"]["password"])
PASSWORD_REQUIREMENTS: dict[str, bool] = {
    "uppercase": settings["user_data_settings"]["requirements"]["password"]["uppercase"],
    "lowercase": settings["user_data_settings"]["requirements"]["password"]["lowercase"],
    "digit": settings["user_data_settings"]["requirements"]["password"]["digit"],
    "special_char": settings["user_data_settings"]["requirements"]["password"]["special_char"]
}
SPECIAL_CHARS: str = r"" + settings["user_data_settings"]["regex"]["special_chars"]

@beartype
def validate_nickname(nickname: Optional[str]):
    errors = []
    
    if not nickname:
        errors.append("Nickname is required.")
    elif len(nickname) < NICKNAME_LENGTH[0]:
        errors.append(f"Nickname must be at least {NICKNAME_LENGTH[0]} characters long.")
    elif len(nickname) > NICKNAME_LENGTH[1]:
        errors.append(f"Nickname must not exceed {NICKNAME_LENGTH[1]} characters.")

    return errors

@beartype
def validate_password(password: Optional[str]):
    errors = []

    if not password:
        errors.append("Password is required.")
    else:
        if len(password) < PASSWORD_LENGTH[0]:
            errors.append(f"Password must be at least {PASSWORD_LENGTH[0]} characters long.")
        elif len(password) > PASSWORD_LENGTH[1]:
            errors.append(f"Password must not exceed {PASSWORD_LENGTH[1]} characters.")
        
        if PASSWORD_REQUIREMENTS["uppercase"] and not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter.")
        if PASSWORD_REQUIREMENTS["lowercase"] and not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter.")
        if PASSWORD_REQUIREMENTS["digit"] and not re.search(r"[0-9]", password):
            errors.append("Password must contain at least one digit.")
        if PASSWORD_REQUIREMENTS["special_char"] and not re.search(SPECIAL_CHARS, password):
            errors.append("Password must contain at least one special character.")

    return errors

@beartype
def validate_register_data(
        nickname: Optional[str],
        password: Optional[str]
    ) -> List[str]:
    errors = []
    
    errors.extend(validate_nickname(nickname))
    errors.extend(validate_password(password))

    return errors