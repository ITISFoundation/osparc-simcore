# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any, Awaitable, Callable

import aiodocker
import pytest
from models_library.docker import DockerLabelKey, StandardSimcoreDockerLabels
from models_library.generated_models.docker_rest_api import Service, Task
from pydantic import ByteSize, ValidationError, parse_obj_as
from simcore_service_clusters_keeper.models import Resources


@pytest.mark.parametrize(
    "a,b,a_greater_or_equal_than_b",
    [
        (
            Resources(cpus=0.2, ram=ByteSize(0)),
            Resources(cpus=0.1, ram=ByteSize(0)),
            True,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(0)),
            Resources(cpus=0.1, ram=ByteSize(0)),
            True,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1)),
            Resources(cpus=0.1, ram=ByteSize(0)),
            True,
        ),
        (
            Resources(cpus=0.05, ram=ByteSize(1)),
            Resources(cpus=0.1, ram=ByteSize(0)),
            False,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(0)),
            Resources(cpus=0.1, ram=ByteSize(1)),
            False,
        ),
    ],
)
def test_resources_ge_operator(
    a: Resources, b: Resources, a_greater_or_equal_than_b: bool
):
    assert (a >= b) is a_greater_or_equal_than_b


@pytest.mark.parametrize(
    "a,b,result",
    [
        (
            Resources(cpus=0, ram=ByteSize(0)),
            Resources(cpus=1, ram=ByteSize(34)),
            Resources(cpus=1, ram=ByteSize(34)),
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(-1)),
            Resources(cpus=1, ram=ByteSize(34)),
            Resources(cpus=1.1, ram=ByteSize(33)),
        ),
    ],
)
def test_resources_add(a: Resources, b: Resources, result: Resources):
    assert a + b == result
    a += b
    assert a == result


@pytest.mark.parametrize(
    "a,b,result",
    [
        (
            Resources(cpus=0, ram=ByteSize(0)),
            Resources(cpus=1, ram=ByteSize(34)),
            Resources.construct(cpus=-1, ram=ByteSize(-34)),
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(-1)),
            Resources(cpus=1, ram=ByteSize(34)),
            Resources.construct(cpus=-0.9, ram=ByteSize(-35)),
        ),
    ],
)
def test_resources_sub(a: Resources, b: Resources, result: Resources):
    assert a - b == result
    a -= b
    assert a == result


async def test_get_simcore_service_docker_labels_from_task_with_missing_labels_raises(
    async_docker_client: aiodocker.Docker,
    create_service: Callable[[dict[str, Any], dict[str, Any], str], Awaitable[Service]],
    task_template: dict[str, Any],
):
    service_missing_osparc_labels = await create_service(task_template, {}, "running")
    assert service_missing_osparc_labels.Spec
    service_tasks = parse_obj_as(
        list[Task],
        await async_docker_client.tasks.list(
            filters={"service": service_missing_osparc_labels.Spec.Name}
        ),
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
    assert service_with_labels.Spec
    service_tasks = parse_obj_as(
        list[Task],
        await async_docker_client.tasks.list(
            filters={"service": service_with_labels.Spec.Name}
        ),
    )
    assert service_tasks
    assert len(service_tasks) == 1
    task_ownership = StandardSimcoreDockerLabels.from_docker_task(service_tasks[0])
    assert task_ownership
    assert task_ownership.user_id == osparc_docker_label_keys.user_id
    assert task_ownership.project_id == osparc_docker_label_keys.project_id
    assert task_ownership.node_id == osparc_docker_label_keys.node_id
