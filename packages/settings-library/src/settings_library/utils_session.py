import base64
import binascii
from typing import Final

DEFAULT_SESSION_COOKIE_NAME: Final[str] = "osparc-sc2"
_32_BYTES_LENGTH: Final[int] = 32


class MixinSessionSettings:
    @classmethod
    def do_check_valid_fernet_key(cls, v):
        """Ensures it is a URL-safe base64-encoded 32-byte valid secret key"""
        # NOTE: was difficult to adjust! See test_session.py::test_session_settings
        value = v.get_secret_value()
        try:
            # SEE https://github.com/pyca/cryptography/blob/main/src/cryptography/fernet.py#L26-L164
            # NOTE: len(v) cannot be 1 more than a multiple of 4
            key_b64decode = base64.urlsafe_b64decode(value)
        except binascii.Error as exc:
            msg = f"Invalid session key {value=}: {exc}"
            raise ValueError(msg) from exc
        if len(key_b64decode) != _32_BYTES_LENGTH:
            msg = (
                f"Invalid session secret {value=} must be 32 url-safe base64-encoded bytes, got {len(key_b64decode)=}."
                'TIP: create new key with python3 -c "from cryptography.fernet import *; print(Fernet.generate_key())"'
            )
            raise ValueError(msg)
        return v
