import secrets
import string


def generate_password(length: int) -> str:
    alphabet = (
        string.digits + string.punctuation.replace('"', "") + string.ascii_letters
    )
    return "".join(secrets.choice(alphabet) for _ in range(length))
