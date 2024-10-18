import secrets
import string
from typing import Any, Final

from pydantic import StrictInt, validate_call

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


def are_secrets_equal(got: str, expected: str) -> bool:
    """Constant-time evaluation of 'got == expected'"""
    return secrets.compare_digest(got.encode("utf8"), expected.encode("utf8"))


@validate_call
def secure_randint(start: StrictInt, end: StrictInt) -> int:
    """Generate a random integer between start (inclusive) and end (exclusive)."""
    if start >= end:
        msg = f"{start=} must be less than {end=}"
        raise ValueError(msg)

    diff = end - start
    return secrets.randbelow(diff) + start


_PLACEHOLDER: Final[str] = "*" * 8
_DEFAULT_SENSITIVE_KEYWORDS: Final[set[str]] = {"pass", "secret"}


def _is_possibly_sensitive(name: str, sensitive_keywords: set[str]) -> bool:
    return any(k.lower() in name.lower() for k in sensitive_keywords)


def mask_sensitive_data(
    data: dict[str, Any], *, extra_sensitive_keywords: set[str] | None = None
) -> dict:
    """Replaces the sensitive values in the dict with a placeholder  before logging

    Sensitive values are detected testing the key name (i.e. a str(key) ) againts sensitive keywords `pass` or `secret`.

    NOTE: this function is used to avoid logging sensitive information like passwords or secrets
    """
    sensitive_keywords = _DEFAULT_SENSITIVE_KEYWORDS | (
        extra_sensitive_keywords or set()
    )
    masked_data: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            masked_data[key] = mask_sensitive_data(
                value, extra_sensitive_keywords=sensitive_keywords
            )
        else:
            masked_data[key] = (
                _PLACEHOLDER
                if _is_possibly_sensitive(f"{key}", sensitive_keywords)
                else value
            )

    return masked_data
