import base64
import binascii
from typing import Annotated, Final

from pydantic import AfterValidator, BeforeValidator, SecretStr

DEFAULT_SESSION_COOKIE_NAME: Final[str] = "osparc-sc2"
_32_BYTES_LENGTH: Final[int] = 32


def _to_secret_str[T](value: T) -> SecretStr | T:
    return SecretStr(value) if isinstance(value, str) else value


def _check_valid_fernet_key(v: SecretStr) -> SecretStr:
    """Ensures it is a URL-safe base64-encoded 32-byte valid secret key"""
    value = v.get_secret_value()
    try:
        # SEE https://github.com/pyca/cryptography/blob/main/src/cryptography/fernet.py#L26-L164
        # NOTE: len(v) cannot be 1 more than a multiple of 4
        key_b64decode = base64.urlsafe_b64decode(value)
    except binascii.Error as exc:
        msg = f"Invalid session key: {exc}"
        raise ValueError(msg) from exc
    if len(key_b64decode) != _32_BYTES_LENGTH:
        msg = (
            "Invalid session secret: must be 32 url-safe base64-encoded bytes, "
            f"got {len(key_b64decode)=}. "
            'TIP: create new key with python3 -c "from cryptography.fernet import *; print(Fernet.generate_key())"'
        )
        raise ValueError(msg)
    return v


SessionSecretKey = Annotated[
    SecretStr,
    AfterValidator(_check_valid_fernet_key),
    BeforeValidator(_to_secret_str),
]
