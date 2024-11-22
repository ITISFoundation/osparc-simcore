# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Awaitable, Callable
from typing import Any

import aiodocker
import pytest
from models_library.docker import DockerLabelKey, StandardSimcoreDockerLabels
from models_library.generated_models.docker_rest_api import Service, Task
from pydantic import TypeAdapter, ValidationError


async def test_get_simcore_service_docker_labels_from_task_with_missing_labels_raises(
    async_docker_client: aiodocker.Docker,
    create_service: Callable[[dict[str, Any], dict[str, Any], str], Awaitable[Service]],
    task_template: dict[str, Any],
):
    service_missing_osparc_labels = await create_service(task_template, {}, "running")
    assert service_missing_osparc_labels.spec
    service_tasks = TypeAdapter(list[Task]).validate_python(
        await async_docker_client.tasks.list(
            filters={"service": service_missing_osparc_labels.spec.name}
        )
    )
    assert service_tasks
    assert len(service_tasks) == 1
    with pytest.raises(ValidationError):
        StandardSimcoreDockerLabels.from_docker_task(service_tasks[0])


async def test_get_simcore_service_docker_labels(
    async_docker_client: aiodocker.Docker,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    osparc_docker_label_keys: StandardSimcoreDockerLabels,
):
    service_with_labels = await create_service(
        task_template,
        osparc_docker_label_keys.to_simcore_runtime_docker_labels(),
        "running",
    )
    assert service_with_labels.spec
    service_tasks = TypeAdapter(list[Task]).validate_python(
        await async_docker_client.tasks.list(
            filters={"service": service_with_labels.spec.name}
        )
    )
    assert service_tasks
    assert len(service_tasks) == 1
    task_ownership = StandardSimcoreDockerLabels.from_docker_task(service_tasks[0])
    assert task_ownership
    assert task_ownership.user_id == osparc_docker_label_keys.user_id
    assert task_ownership.project_id == osparc_docker_label_keys.project_id
    assert task_ownership.node_id == osparc_docker_label_keys.node_id
