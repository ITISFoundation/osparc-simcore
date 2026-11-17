from typing import Final

import pytest
from pydantic import ValidationError
from simcore_service_webserver.session.settings import SessionSettings

_SECRET: Final[str] = "s3cr3t-SENTINEL" + "A" * 40


def test_malformed_session_secret_key_not_exposed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WEBSERVER_SESSION_SECRET_KEY", _SECRET)

    with pytest.raises(ValidationError) as exc_info:
        SessionSettings.create_from_envs()

    error = exc_info.value
    assert _SECRET not in f"{error}"
    assert _SECRET not in repr(error.errors())
    assert _SECRET not in error.json()
