import werkzeug.security as w_security
from beartype import beartype

@beartype
def generate_password_hash(password: str) -> str:
    return w_security.generate_password_hash(
        password, 
        method='pbkdf2:sha512', 
        salt_length=34
    )[::-1]

@beartype
def check_password_hash(password_hash: str, password: str) -> bool:
    return w_security.check_password_hash(password_hash[::-1], password)