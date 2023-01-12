import secrets
import string
from typing import Final

MIN_PASSWORD_LENGTH = 30
_SAFE_SYMBOLS = "!$%*+,-.:=?@^_~"  # avoid issues with parsing, espapes etc
_ALPHABET: Final = string.digits + _SAFE_SYMBOLS + string.ascii_letters


def generate_password(length: int = MIN_PASSWORD_LENGTH) -> str:
    """Generates a password of at least MIN_PASSWORD_LENGTH"""
    length = max(length, MIN_PASSWORD_LENGTH)
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))
