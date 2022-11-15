# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any, Awaitable, Callable, Iterator, Mapping

import aiodocker
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


async def test_check_dynamic_resources_with_no_services_does_nothing(
    docker_swarm: None,
    disable_dynamic_service_background_task: None,
    initialized_app: FastAPI,
):
    await check_dynamic_resources(initialized_app)
    # TODO: assert nothing is actually done!


async def test_check_dynamic_resources_with_service_with_lack_of_resources(
    async_docker_client: aiodocker.Docker,
    docker_swarm: None,
    disable_dynamic_service_background_task: None,
    initialized_app: FastAPI,
    create_service: Callable[[dict[str, Any]], Awaitable[Mapping[str, Any]]],
    task_template: dict[str, Any],
    create_task_resources: Callable[[int], dict[str, Any]],
    assert_for_service_state: Callable[
        [aiodocker.Docker, Mapping[str, Any], list[str]], Awaitable[None]
    ],
):
    task_template_with_too_many_resource = task_template | create_task_resources(1000)
    service_with_too_many_resources = await create_service(
        task_template_with_too_many_resource
    )
    await assert_for_service_state(
        async_docker_client,
        service_with_too_many_resources,
        ["pending"],
    )
    await check_dynamic_resources(initialized_app)
