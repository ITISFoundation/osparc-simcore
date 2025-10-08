# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable
from functools import partial
from typing import Any

import pytest
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.typing_mock import HandlerMockFactory


@pytest.fixture
def app_environment(
    app_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    # NOTE: overrides app_environment
    monkeypatch.setenv("WEBSERVER_GARBAGE_COLLECTOR", "null")
    return app_environment | {"WEBSERVER_GARBAGE_COLLECTOR": "null"}


def _result_or_exception_side_effect(result_or_exception, *args, **kwargs):
    if isinstance(result_or_exception, Exception):
        raise result_or_exception

    return result_or_exception


@pytest.fixture()
def mock_handler_in_storage_rest(
    mocker: MockerFixture,
) -> HandlerMockFactory:
    def _create(
        handler_name: str,
        return_value: Any = None,
        exception: Exception | None = None,
        side_effect: Callable | None = None,
    ) -> MockType:

        from simcore_service_webserver.storage import _rest

        assert exception is None or side_effect is None

        return mocker.patch.object(
            _rest,
            handler_name,
            return_value=return_value,
            side_effect=partial(_result_or_exception_side_effect, side_effect),
        )

    return _create


@pytest.fixture()
def mock_handler_in_task_service(
    mocker: MockerFixture,
) -> HandlerMockFactory:
    def _create(
        handler_name: str,
        return_value: Any = None,
        exception: Exception | None = None,
        side_effect: Callable | None = None,
    ) -> MockType:

        from simcore_service_webserver.tasks import (
            _tasks_service,
        )

        assert exception is None or side_effect is None

        return mocker.patch.object(
            _tasks_service,
            handler_name,
            return_value=return_value,
            side_effect=partial(_result_or_exception_side_effect, side_effect),
        )

    return _create
