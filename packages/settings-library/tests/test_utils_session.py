import base64
import traceback
from collections.abc import Callable
from typing import Annotated, Final

import pytest
from annotated_types import doc
from pydantic import Field, SecretStr, ValidationError
from settings_library.base import BaseCustomSettings
from settings_library.utils_session import SessionSecretKey

_PLAINTEXT: Final[Annotated[str, doc("unique enough not to appear by accident in an error report")]] = "s3cr3t-SENTINEL"
_INVALID_BASE64_KEY: Final[Annotated[str, doc(">= min_length so the fernet check runs; '!' fails base64 decoding")]] = (
    "A" * 43 + "!" + _PLAINTEXT
)
_INVALID_LENGTH_KEY: Final[
    Annotated[str, doc("valid base64 (44 chars) decoding to 31 bytes; doubles as the sentinel")]
] = base64.urlsafe_b64encode(b"K" * 31).decode()


class _SessionSettings(BaseCustomSettings):
    SESSION_SECRET_KEY: Annotated[
        SessionSecretKey,
        Field(..., min_length=44),
    ]
    SESSION_PORT: int = Field(default=8080)


_RENDERERS: Final[dict[str, Callable[[ValidationError], str]]] = {
    "str": str,
    "errors": lambda e: repr(e.errors()),
    "json": lambda e: e.json(),
}


def _validation_error(bad_key: str) -> ValidationError:
    with pytest.raises(ValidationError) as exc_info:
        _SessionSettings(SESSION_SECRET_KEY=bad_key)  # pyright: ignore[reportArgumentType]
    return exc_info.value


@pytest.mark.parametrize("bad_key", [_INVALID_BASE64_KEY, _INVALID_LENGTH_KEY])
@pytest.mark.parametrize("renderer", list(_RENDERERS))
def test_rejected_key_never_exposed(bad_key: str, renderer: str):
    error = _validation_error(bad_key)
    assert bad_key not in _RENDERERS[renderer](error)


@pytest.mark.parametrize("bad_key", [_INVALID_BASE64_KEY, _INVALID_LENGTH_KEY])
def test_rejected_key_input_is_masked(bad_key: str):
    (error,) = _validation_error(bad_key).errors()
    assert isinstance(error["input"], SecretStr)
    assert str(error["input"]) == "**********"


def test_diagnostic_survives_masking():
    # the length error tells the operator what is wrong without echoing the key
    with pytest.raises(ValidationError) as exc_info:
        _SessionSettings(SESSION_SECRET_KEY=_INVALID_LENGTH_KEY)  # pyright: ignore[reportArgumentType]
    assert "must be 32 url-safe base64-encoded bytes" in str(exc_info.value)

    rendered_traceback = "".join(traceback.format_exception(exc_info.value))
    assert _INVALID_LENGTH_KEY not in rendered_traceback


def test_non_string_input_still_reported():
    # type errors keep their (non-secret) input: debugging info is not lost
    with pytest.raises(ValidationError) as exc_info:
        _SessionSettings(SESSION_SECRET_KEY=123)  # pyright: ignore[reportArgumentType]
    (error,) = exc_info.value.errors()
    assert error["type"] == "string_type"
    assert error["input"] == 123


def test_valid_fernet_key_passes_through():
    valid_key = base64.urlsafe_b64encode(b"K" * 32).decode()
    settings = _SessionSettings(SESSION_SECRET_KEY=valid_key)  # pyright: ignore[reportArgumentType]
    assert settings.SESSION_SECRET_KEY.get_secret_value() == valid_key
    assert valid_key not in repr(settings)


def test_key_error_grouped_with_other_field_errors():
    # the validator raises ValueError so pydantic collects every field error
    # of the model into a single ValidationError at boot
    with pytest.raises(ValidationError) as exc_info:
        _SessionSettings(
            SESSION_SECRET_KEY=_INVALID_LENGTH_KEY,  # pyright: ignore[reportArgumentType]
            SESSION_PORT="not-an-int",  # pyright: ignore[reportArgumentType]
        )
    locations = {error["loc"][0] for error in exc_info.value.errors()}
    assert locations == {"SESSION_SECRET_KEY", "SESSION_PORT"}
