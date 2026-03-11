# pylint:disable=redefined-outer-name

from typing import Final
from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

_MODULE: Final["str"] = "simcore_service_dynamic_scheduler.api.frontend.routes_external_scheduler._service"


@pytest.fixture
def use_internal_scheduler() -> bool:
    return False


@pytest.fixture
def mock_stop_dynamic_service(mocker: MockerFixture) -> AsyncMock:
    async_mock = AsyncMock()
    mocker.patch(f"{_MODULE}.stop_dynamic_service", async_mock)
    return async_mock


@pytest.fixture
def mock_remove_tracked_service(mocker: MockerFixture) -> AsyncMock:
    async_mock = AsyncMock()
    mocker.patch(f"{_MODULE}.remove_tracked_service", async_mock)
    return async_mock
