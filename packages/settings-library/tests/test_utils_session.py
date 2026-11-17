import base64
import traceback
from typing import Annotated

import pytest
from pydantic import Field, SecretStr, ValidationError, field_validator
from settings_library.base import BaseCustomSettings
from settings_library.utils_session import MixinSessionSettings

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
    with pytest.raises(ValueError, match=expected_in_message) as exc_info:
        MixinSessionSettings.do_check_valid_fernet_key(SecretStr(bad_key))

    assert bad_key not in str(exc_info.value)
    rendered_traceback = "".join(traceback.format_exception(exc_info.value))
    assert bad_key not in rendered_traceback


def test_valid_fernet_key_passes_through():
    valid_key = SecretStr(base64.urlsafe_b64encode(b"K" * 32).decode())
    assert MixinSessionSettings.do_check_valid_fernet_key(valid_key) is valid_key


class _SessionSettings(BaseCustomSettings, MixinSessionSettings):
    SESSION_SECRET_KEY: Annotated[SecretStr, Field(..., min_length=44)]
    SESSION_PORT: int = Field(default=8080)

    @field_validator("SESSION_SECRET_KEY")
    @classmethod
    def _check_valid_fernet_key(cls, v: SecretStr) -> SecretStr:
        return cls.do_check_valid_fernet_key(v)


def test_fernet_key_not_leaked_in_settings_validation():
    with pytest.raises(ValidationError) as exc_info:
        _SessionSettings(SESSION_SECRET_KEY=_INVALID_LENGTH_KEY)  # pyright: ignore[reportArgumentType]

    rendered = str(exc_info.value)
    assert _INVALID_LENGTH_KEY not in rendered
    assert "input_value" not in rendered
    rendered_traceback = "".join(traceback.format_exception(exc_info.value))
    assert _INVALID_LENGTH_KEY not in rendered_traceback


def test_session_key_error_grouped_with_other_field_errors():
    # the validator must raise ValueError (not e.g. RuntimeError) so that pydantic
    # collects every field error of the model into a single ValidationError at boot
    with pytest.raises(ValidationError) as exc_info:
        _SessionSettings(
            SESSION_SECRET_KEY=_INVALID_LENGTH_KEY,  # pyright: ignore[reportArgumentType]
            SESSION_PORT="not-an-int",  # pyright: ignore[reportArgumentType]
        )

    locations = {err["loc"][0] for err in exc_info.value.errors()}
    assert locations == {"SESSION_SECRET_KEY", "SESSION_PORT"}
