# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any, Awaitable, Callable, Mapping

import aiodocker
import pytest
from fastapi import status
from simcore_service_autoscaling.utils_docker import (
    eval_cluster_resources,
    pending_services_with_insufficient_resources,
)


async def test_eval_cluster_resource_without_swarm():
    with pytest.raises(aiodocker.DockerError) as exc_info:
        await pending_services_with_insufficient_resources()

    assert exc_info.value.status == status.HTTP_503_SERVICE_UNAVAILABLE

    with pytest.raises(aiodocker.DockerError) as exc_info:
        await eval_cluster_resources()

    assert exc_info.value.status == status.HTTP_503_SERVICE_UNAVAILABLE


async def test_pending_services_with_insufficient_resources_with_no_service(
    docker_swarm: None,
):
    assert await pending_services_with_insufficient_resources() == False


async def test_pending_services_with_insufficient_resources_with_service_lacking_resource(
    docker_swarm: None,
    async_docker_client: aiodocker.Docker,
    create_service: Callable[[dict[str, Any]], Awaitable[Mapping[str, Any]]],
    task_template: dict[str, Any],
    create_task_resources: Callable[[int], dict[str, Any]],
):
    service_with_no_resources = await create_service(task_template)
    await pytest.helpers.assert_for_service_state(
        async_docker_client, service_with_no_resources, expected_states=["running"]
    )
    assert await pending_services_with_insufficient_resources() == False
    task_template_with_too_many_resource = task_template | create_task_resources(1000)
    service_with_too_many_resources = await create_service(
        task_template_with_too_many_resource
    )
    await pytest.helpers.assert_for_service_state(
        async_docker_client,
        service_with_too_many_resources,
        expected_states=["pending"],
    )
    assert await pending_services_with_insufficient_resources() == True
