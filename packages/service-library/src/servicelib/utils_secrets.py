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


_MIN_SECRET_NUM_BYTES = 32


def generate_token_secret_key(nbytes: int = _MIN_SECRET_NUM_BYTES) -> str:
    """Equivalent to generating a random password with openssl in hex format
    openssl rand -hex 32
    """
    return secrets.token_hex(nbytes)


MIN_PASSCODE_LENGTH = 6


def generate_passcode(number_of_digits: int = MIN_PASSCODE_LENGTH) -> str:
    """Generates a numerical code of a least MIN_PASSCODE_LENGTH.

    Numbers with less digits will add leading zeros
    e.g. if the code is 100 it will return "000100"

    NOTE: 6 digits is recommended by NIST (National Institute of Standards and Technology) in
    their guideline for Two-factor authentication.
    They consider that 6 digits one-time password (OTP) provides an acceptable level of security.
    """
    number_of_digits = max(number_of_digits, MIN_PASSCODE_LENGTH)
    passcode = secrets.randbelow(10**number_of_digits)
    return f"{passcode}".zfill(number_of_digits)


def compare_secrets(got: str, expected: str) -> bool:
    """Constant-time evaluation of 'got == expected'"""
    return secrets.compare_digest(got.encode("utf8"), expected.encode("utf8"))
