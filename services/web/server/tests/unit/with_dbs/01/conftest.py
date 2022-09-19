# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from pytest import MonkeyPatch


@pytest.fixture
def app_environment(
    app_environment: dict[str, str], monkeypatch: MonkeyPatch
) -> dict[str, str]:
    # NOTE: overrides app_environment
    monkeypatch.setenv("WEBSERVER_GARBAGE_COLLECTOR", "null")
    return app_environment | {"WEBSERVER_GARBAGE_COLLECTOR": "null"}
