# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any, Awaitable, Callable, Mapping

import aiodocker
import pytest
from models_library.generated_models.docker_rest_api import Task
from pydantic import ByteSize, ValidationError, parse_obj_as
from simcore_service_autoscaling.models import Resources, SimcoreServiceDockerLabelKeys


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
            Resources(cpus=0, ram=0),
            Resources(cpus=1, ram=34),
            Resources(cpus=1, ram=34),
        ),
        (
            Resources(cpus=0.1, ram=-1),
            Resources(cpus=1, ram=34),
            Resources(cpus=1.1, ram=33),
        ),
    ],
)
def test_resources_add(a: Resources, b: Resources, result: Resources):
    assert a + b == result
    a += b
    assert a == result


async def test_get_simcore_service_docker_labels_from_task_with_missing_labels_raises(
    async_docker_client: aiodocker.Docker,
    create_service: Callable[
        [dict[str, Any], dict[str, Any], str], Awaitable[Mapping[str, Any]]
    ],
    task_template: dict[str, Any],
):
    service_missing_osparc_labels = await create_service(task_template, {}, "running")
    service_tasks = parse_obj_as(
        list[Task],
        await async_docker_client.tasks.list(
            filters={"service": service_missing_osparc_labels["Spec"]["Name"]}
        ),
    )
    assert service_tasks
    assert len(service_tasks) == 1
    with pytest.raises(ValidationError):
        SimcoreServiceDockerLabelKeys.from_docker_task(service_tasks[0])


def test_osparc_docker_label_keys_to_docker_labels(
    osparc_docker_label_keys: SimcoreServiceDockerLabelKeys,
):
    exported_dict = osparc_docker_label_keys.to_docker_labels()
    assert all(isinstance(v, str) for v in exported_dict.values())
    assert parse_obj_as(SimcoreServiceDockerLabelKeys, exported_dict)


async def test_get_simcore_service_docker_labels(
    async_docker_client: aiodocker.Docker,
    create_service: Callable[
        [dict[str, Any], dict[str, str], str], Awaitable[Mapping[str, Any]]
    ],
    task_template: dict[str, Any],
    osparc_docker_label_keys: SimcoreServiceDockerLabelKeys,
):
    service_with_labels = await create_service(
        task_template, osparc_docker_label_keys.to_docker_labels(), "running"
    )
    service_tasks = parse_obj_as(
        list[Task],
        await async_docker_client.tasks.list(
            filters={"service": service_with_labels["Spec"]["Name"]}
        ),
    )
    assert service_tasks
    assert len(service_tasks) == 1
    task_ownership = SimcoreServiceDockerLabelKeys.from_docker_task(service_tasks[0])
    assert task_ownership
    assert task_ownership.user_id == osparc_docker_label_keys.user_id
    assert task_ownership.project_id == osparc_docker_label_keys.project_id
    assert task_ownership.node_id == osparc_docker_label_keys.node_id
