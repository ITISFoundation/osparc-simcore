# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Awaitable, Callable
from unittest import mock

import pytest
import requests_mock
from fastapi import FastAPI
from simcore_service_resource_usage_tracker.prometheus_containers.cli_placeholder import (
    collect_service_resource_usage_task,
)


@pytest.fixture
def minimal_configuration(
    mocked_prometheus_with_query: requests_mock.Mocker,
    mocked_redis_server: None,
    disabled_tracker_background_task: dict[str, mock.Mock],
    initialized_app: FastAPI,
) -> None:
    assert initialized_app
    disabled_tracker_background_task["start_task"].assert_called_once()


@pytest.fixture
def trigger_collect_service_resource_usage(
    initialized_app: FastAPI,
) -> Callable[[], Awaitable[None]]:
    async def _triggerer() -> None:
        return await collect_service_resource_usage_task(initialized_app)

    return _triggerer


@pytest.mark.skip(
    reason="This test is currently not needed, as setup_background_task is commented out in application.py"
)
async def test_triggering(
    disabled_database: None,
    disabled_rabbitmq: None,
    minimal_configuration: None,
    mocked_prometheus_with_query: requests_mock.Mocker,
    trigger_collect_service_resource_usage: Callable[[], Awaitable[None]],
):
    await trigger_collect_service_resource_usage()
