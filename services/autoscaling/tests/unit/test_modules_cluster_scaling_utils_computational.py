# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from aws_library.ec2 import Resources
from dask_task_models_library.resource_constraints import (
    DASK_WORKER_THREAD_RESOURCE_NAME,
)
from pydantic import ByteSize, TypeAdapter
from simcore_service_autoscaling.models import DaskTask, DaskTaskResources
from simcore_service_autoscaling.modules.cluster_scaling._utils_computational import (
    _DEFAULT_MAX_CPU,
    _DEFAULT_MAX_RAM,
    resources_from_dask_task,
)


@pytest.mark.parametrize(
    "dask_task, expected_resource",
    [
        pytest.param(
            DaskTask(task_id="fake", required_resources=DaskTaskResources()),
            Resources(
                cpus=_DEFAULT_MAX_CPU,
                ram=TypeAdapter(ByteSize).validate_python(_DEFAULT_MAX_RAM),
                generic_resources={DASK_WORKER_THREAD_RESOURCE_NAME: 1},
            ),
            id="missing resources returns defaults",
        ),
        pytest.param(
            DaskTask(task_id="fake", required_resources={"CPU": 2.5}),
            Resources(
                cpus=2.5,
                ram=TypeAdapter(ByteSize).validate_python(_DEFAULT_MAX_RAM),
                generic_resources={DASK_WORKER_THREAD_RESOURCE_NAME: 1},
            ),
            id="only cpus defined",
        ),
        pytest.param(
            DaskTask(
                task_id="fake",
                required_resources={"CPU": 2.5, "RAM": 2 * 1024 * 1024 * 1024},
            ),
            Resources(
                cpus=2.5,
                ram=TypeAdapter(ByteSize).validate_python("2GiB"),
                generic_resources={DASK_WORKER_THREAD_RESOURCE_NAME: 1},
            ),
            id="cpu and ram defined",
        ),
        pytest.param(
            DaskTask(
                task_id="fake",
                required_resources={"CPU": 2.5, "xram": 2 * 1024 * 1024 * 1024},  # type: ignore
            ),
            Resources(
                cpus=2.5,
                ram=TypeAdapter(ByteSize).validate_python(_DEFAULT_MAX_RAM),
                generic_resources={
                    DASK_WORKER_THREAD_RESOURCE_NAME: 1,
                    "xram": 2 * 1024 * 1024 * 1024,
                },
            ),
            id="invalid naming",
        ),
    ],
)
def test_resources_from_dask_task(dask_task: DaskTask, expected_resource: Resources):
    assert resources_from_dask_task(dask_task) == expected_resource
