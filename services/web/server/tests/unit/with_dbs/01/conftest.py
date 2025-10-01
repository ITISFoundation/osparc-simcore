# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable
from typing import Any

import pytest
from pytest_mock import MockerFixture


@pytest.fixture
def app_environment(
    app_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    # NOTE: overrides app_environment
    monkeypatch.setenv("WEBSERVER_GARBAGE_COLLECTOR", "null")
    return app_environment | {"WEBSERVER_GARBAGE_COLLECTOR": "null"}


@pytest.fixture
def create_backend_mock(
    mocker: MockerFixture,
) -> Callable[[str, str, Any], None]:
    def _(module: str, method: str, result_or_exception: Any):
        def side_effect(*args, **kwargs):
            if isinstance(result_or_exception, Exception):
                raise result_or_exception

            return result_or_exception

        for fct in (f"{module}.{method}",):
            mocker.patch(fct, side_effect=side_effect)

    return _
