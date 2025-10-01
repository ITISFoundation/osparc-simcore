import datetime as dt
import hashlib
import re
import secrets
import string
from typing import Annotated, Final

from models_library.basic_types import IDStr
from pydantic import BaseModel, ConfigDict, Field

_PUNCTUATION_REGEX = re.compile(
    pattern="[" + re.escape(string.punctuation.replace("_", "")) + "]"
)

_KEY_LEN: Final = 10
_SECRET_LEN: Final = 20


# Application-wide pepper/salt for PBKDF2 (should ideally be kept secret and configurable)
_API_KEY_PEPPER: Final = b"models-library-api-key-pepper-CHANGE_ME"
_API_KEY_HASH_ITERATIONS: Final = 100_000

def generate_api_key_prefix(name: str) -> str:
    return _PUNCTUATION_REGEX.sub("_", name[:5])


def generate_unique_api_key(name: str, length: int = _KEY_LEN) -> str:
    prefix = generate_api_key_prefix(name)
    # Use PBKDF2-HMAC-SHA256 with an application-wide pepper (salt) and high iteration count
    hashed = hashlib.pbkdf2_hmac(
        "sha256", 
        name.encode(), 
        _API_KEY_PEPPER, 
        _API_KEY_HASH_ITERATIONS,
    ).hex()
    return f"{prefix}_{hashed[:length]}"


def generate_api_key_and_secret(name: str):
    api_key = generate_unique_api_key(name)
    api_secret = secrets.token_hex(_SECRET_LEN)
    return api_key, api_secret


class ApiKeyCreate(BaseModel):
    display_name: Annotated[str, Field(..., min_length=3)]
    expiration: dt.timedelta | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )


class ApiKeyGet(BaseModel):
    id: IDStr
    display_name: Annotated[str, Field(..., min_length=3)]
    api_key: str | None = None
    api_secret: str | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "42",
                    "display_name": "test-api-forever",
                    "api_key": "key",
                    "api_secret": "secret",
                },
            ]
        },
    )
