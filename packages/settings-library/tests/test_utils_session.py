import base64
import traceback
from typing import Annotated

import pytest
from pydantic import Field, SecretStr, field_validator
from settings_library.base import BaseCustomSettings
from settings_library.utils_session import InvalidSessionSecretKeyError, MixinSessionSettings

_INVALID_LENGTH_KEY: str = base64.urlsafe_b64encode(b"K" * 31).decode()
_INVALID_BASE64_KEY: str = "A" * 43 + "!"


@pytest.mark.parametrize(
    "bad_key,expected_in_message",
    [
        pytest.param(_INVALID_BASE64_KEY, "Invalid session key", id="non-base64"),
        pytest.param(_INVALID_LENGTH_KEY, "Invalid session secret", id="wrong-length"),
    ],
)
def test_fernet_key_not_leaked_in_validation_error(bad_key: str, expected_in_message: str):
    with pytest.raises(InvalidSessionSecretKeyError, match=expected_in_message) as exc_info:
        MixinSessionSettings.do_check_valid_fernet_key(SecretStr(bad_key))

    assert bad_key not in str(exc_info.value)
    rendered_traceback = "".join(traceback.format_exception(exc_info.value))
    assert bad_key not in rendered_traceback


def test_valid_fernet_key_passes_through():
    valid_key = SecretStr(base64.urlsafe_b64encode(b"K" * 32).decode())
    assert MixinSessionSettings.do_check_valid_fernet_key(valid_key) is valid_key


def test_fernet_key_not_leaked_in_settings_validation():
    class _SessionSettings(BaseCustomSettings, MixinSessionSettings):
        SESSION_SECRET_KEY: Annotated[SecretStr, Field(..., min_length=44)]

        @field_validator("SESSION_SECRET_KEY")
        @classmethod
        def _check_valid_fernet_key(cls, v: SecretStr) -> SecretStr:
            return cls.do_check_valid_fernet_key(v)

    # not wrapped in pydantic's ValidationError, which would echo the raw
    # input_value (the key) in its repr
    with pytest.raises(InvalidSessionSecretKeyError) as exc_info:
        # str input, as when the value comes from the environment
        _SessionSettings(SESSION_SECRET_KEY=_INVALID_LENGTH_KEY)  # pyright: ignore[reportArgumentType]

    rendered_traceback = "".join(traceback.format_exception(exc_info.value))
    assert _INVALID_LENGTH_KEY not in rendered_traceback
