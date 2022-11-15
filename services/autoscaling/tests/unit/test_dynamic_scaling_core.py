# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Iterator

import pytest
from fastapi import FastAPI
from pytest_mock.plugin import MockerFixture
from simcore_service_autoscaling.dynamic_scaling_core import check_dynamic_resources


@pytest.fixture
def disable_dynamic_service_background_task(mocker: MockerFixture) -> Iterator[None]:
    mocker.patch(
        "simcore_service_autoscaling.dynamic_scaling.start_background_task",
        autospec=True,
    )

    mocker.patch(
        "simcore_service_autoscaling.dynamic_scaling.stop_background_task",
        autospec=True,
    )

    yield


async def test_check_dynamic_resources(
    docker_swarm: None,
    disable_dynamic_service_background_task: None,
    initialized_app: FastAPI,
):
    await check_dynamic_resources(initialized_app)
