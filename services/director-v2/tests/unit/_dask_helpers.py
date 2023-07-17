# pylint:disable=unused-variable
# pylint:disable=unused-argument

from typing import Any, NamedTuple

from dask_gateway_server.app import DaskGateway
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.io import (
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from dask_task_models_library.container_tasks.protocol import (
    ContainerCommands,
    ContainerImage,
    ContainerTag,
    LogFileUploadURL,
)


class DaskGatewayServer(NamedTuple):
    address: str
    proxy_address: str
    password: str
    server: DaskGateway


def fake_sidecar_fct(
    docker_auth: DockerBasicAuth,
    service_key: ContainerImage,
    service_version: ContainerTag,
    input_data: TaskInputData,
    output_data_keys: TaskOutputDataSchema,
    log_file_url: LogFileUploadURL,
    command: ContainerCommands,
    expected_annotations: dict[str, Any],
) -> TaskOutputData:
    import time

    from dask.distributed import get_worker

    # sleep a bit in case someone is aborting us
    time.sleep(1)

    # get the task data
    worker = get_worker()
    task = worker.state.tasks.get(worker.get_current_task())
    assert task is not None
    assert task.annotations == expected_annotations

    return TaskOutputData.parse_obj({"some_output_key": 123})


def fake_failing_sidecar_fct(
    docker_auth: DockerBasicAuth,
    service_key: ContainerImage,
    service_version: ContainerTag,
    input_data: TaskInputData,
    output_data_keys: TaskOutputDataSchema,
    log_file_url: LogFileUploadURL,
    command: ContainerCommands,
) -> TaskOutputData:
    err_msg = "sadly we are failing to execute anything cause we are dumb..."
    raise ValueError(err_msg)
