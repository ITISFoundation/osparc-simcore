# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from functools import partial
from typing import Any

import pytest
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.typing_mock import HandlerMockFactory
from simcore_service_webserver.storage import _rest
from simcore_service_webserver.tasks import _tasks_service


@pytest.fixture
def app_environment(
    app_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    # NOTE: overrides app_environment
    monkeypatch.setenv("WEBSERVER_GARBAGE_COLLECTOR", "null")
    return app_environment | {"WEBSERVER_GARBAGE_COLLECTOR": "null"}


def _result_or_exception_side_effect(result_or_exception: Any, *args, **kwargs):
    if isinstance(result_or_exception, Exception):
        raise result_or_exception

    return result_or_exception


def _create_handler_mock_factory(
    mocker: MockerFixture, module: Any
) -> HandlerMockFactory:
    def _create(
        handler_name: str,
        return_value: Any = None,
        exception: Exception | None = None,
        side_effect: Any | None = None,
    ) -> MockType:

        assert exception is None or side_effect is None

        return mocker.patch.object(
            module,
            handler_name,
            return_value=return_value,
            side_effect=(
                partial(_result_or_exception_side_effect, side_effect)
                if side_effect
                else None
            ),
        )

    return _create


@pytest.fixture()
def mock_handler_in_storage_rest(
    mocker: MockerFixture,
) -> HandlerMockFactory:
    return _create_handler_mock_factory(mocker, _rest)


@pytest.fixture()
def mock_handler_in_task_service(
    mocker: MockerFixture,
) -> HandlerMockFactory:
    return _create_handler_mock_factory(mocker, _tasks_service)
