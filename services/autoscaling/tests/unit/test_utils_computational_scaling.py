# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from aws_library.ec2 import Resources
from pydantic import ByteSize, TypeAdapter
from simcore_service_autoscaling.models import DaskTask, DaskTaskResources
from simcore_service_autoscaling.utils.computational_scaling import (
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
            ),
            id="missing resources returns defaults",
        ),
        pytest.param(
            DaskTask(task_id="fake", required_resources={"CPU": 2.5}),
            Resources(
                cpus=2.5, ram=TypeAdapter(ByteSize).validate_python(_DEFAULT_MAX_RAM)
            ),
            id="only cpus defined",
        ),
        pytest.param(
            DaskTask(
                task_id="fake",
                required_resources={"CPU": 2.5, "RAM": 2 * 1024 * 1024 * 1024},
            ),
            Resources(cpus=2.5, ram=TypeAdapter(ByteSize).validate_python("2GiB")),
            id="cpu and ram defined",
        ),
        pytest.param(
            DaskTask(
                task_id="fake",
                required_resources={"CPU": 2.5, "ram": 2 * 1024 * 1024 * 1024},
            ),
            Resources(
                cpus=2.5, ram=TypeAdapter(ByteSize).validate_python(_DEFAULT_MAX_RAM)
            ),
            id="invalid naming",
        ),
    ],
)
def test_resources_from_dask_task(dask_task: DaskTask, expected_resource: Resources):
    assert resources_from_dask_task(dask_task) == expected_resource
