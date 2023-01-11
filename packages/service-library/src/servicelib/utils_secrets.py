import secrets
import string

MIN_PASSWORD_LENGTH = 30


def generate_password(length: int = MIN_PASSWORD_LENGTH) -> str:
    """Generates a password of at least MIN_PASSWORD_LENGTH"""
    length = max(length, MIN_PASSWORD_LENGTH)
    alphabet = string.digits + "!#$%&()*+,-./:;<=>?@^_{|}~" + string.ascii_letters
    return "".join(secrets.choice(alphabet) for _ in range(length))
