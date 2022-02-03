import base64
import binascii

from pydantic.class_validators import validator
from pydantic.fields import Field
from pydantic.types import SecretStr
from settings_library.base import BaseCustomSettings


class SessionSettings(BaseCustomSettings):

    SESSION_SECRET_KEY: SecretStr = Field(
        ...,
        description="Secret key to encrypt cookies. "
        'TIP: python3 -c "from cryptography.fernet import *; print(Fernet.generate_key())"',
        min_length=44,
        env=["SESSION_SECRET_KEY", "WEBSERVER_SESSION_SECRET_KEY"],
    )

    @validator("SESSION_SECRET_KEY")
    @classmethod
    def check_valid_fernet_key(cls, v):
        """Ensures it is a URL-safe base64-encoded 32-byte valid secret key"""
        # NOTE: was difficult to adjust! See test_session.py::test_session_settings
        value = v.get_secret_value()
        try:
            # SEE https://github.com/pyca/cryptography/blob/main/src/cryptography/fernet.py#L26-L164
            # NOTE: len(v) cannot be 1 more than a multiple of 4
            key_b64decode = base64.urlsafe_b64decode(value)
        except binascii.Error as exc:
            raise ValueError(f"Invalid session key {value=}: {exc}") from exc
        if len(key_b64decode) != 32:
            raise ValueError(
                f"Invalid session secret {value=} must be 32 url-safe base64-encoded bytes, got {len(key_b64decode)=}."
                'TIP: create new key with python3 -c "from cryptography.fernet import *; print(Fernet.generate_key())"'
            )
        return v


def assert_valid_config(secret_key: str):

    WEBSERVER_SESSION = SessionSettings()
    assert (  # nosec
        WEBSERVER_SESSION.SESSION_SECRET_KEY.get_secret_value() == secret_key
    )  # nosec
