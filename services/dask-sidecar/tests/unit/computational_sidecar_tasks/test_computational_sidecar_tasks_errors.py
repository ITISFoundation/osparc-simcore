# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member
# pylint: disable=too-many-arguments

from collections.abc import Callable
from unittest import mock

import distributed
import pytest
from dask_task_models_library.container_tasks.errors import (
    ServiceInputsUseFileToKeyMapButReceivesZipDataError,
    ServiceOutOfMemoryError,
    ServiceRuntimeError,
)
from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.dask_sidecar_tasks import (
    ServiceExampleParam,
    run_cpu_no_parent_node,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dask_sidecar.computational_sidecar.errors import (
    ServiceBadFormattedOutputError,
)
from simcore_service_dask_sidecar.worker import run_computational_sidecar

pytest_simcore_core_services_selection = [
    "rabbit",
]


@run_cpu_no_parent_node
def test_failing_service_raises_exception(
    caplog_info_level: pytest.LogCaptureFixture,
    app_environment: EnvVarsDict,
    dask_subsystem_mock: dict[str, mock.Mock],
    failing_ubuntu_task: ServiceExampleParam,
    mocked_get_image_labels: mock.Mock,
):
    with pytest.raises(ServiceRuntimeError):
        run_computational_sidecar(**failing_ubuntu_task.sidecar_params())


@run_cpu_no_parent_node
def test_running_service_that_generates_unexpected_data_raises_exception(
    caplog_info_level: pytest.LogCaptureFixture,
    app_environment: EnvVarsDict,
    dask_subsystem_mock: dict[str, mock.Mock],
    sleeper_task_unexpected_output: ServiceExampleParam,
):
    with pytest.raises(ServiceBadFormattedOutputError):
        run_computational_sidecar(
            **sleeper_task_unexpected_output.sidecar_params(),
        )


@run_cpu_no_parent_node
def test_running_service_with_incorrect_zip_data_that_uses_a_file_to_key_map_raises_exception(
    caplog_info_level: pytest.LogCaptureFixture,
    app_environment: EnvVarsDict,
    dask_subsystem_mock: dict[str, mock.Mock],
    task_with_file_to_key_map_in_input_data: ServiceExampleParam,
):
    with pytest.raises(ServiceInputsUseFileToKeyMapButReceivesZipDataError):
        run_computational_sidecar(
            **task_with_file_to_key_map_in_input_data.sidecar_params(),
        )


# now a test that checks if a service goes out of memory
@run_cpu_no_parent_node
def test_run_sidecar_with_service_exceeding_memory_limit(
    app_environment: EnvVarsDict,
    dask_client: distributed.Client,
    sidecar_task: Callable[..., ServiceExampleParam],
    mocked_get_image_labels: mock.Mock,
):
    # Configure the task to exceed memory limit
    # NOTE: We allocate memory gradually (1MB chunks in a loop) instead of a single
    # large bytearray to ensure pages are actually committed and the kernel OOM killer
    # fires reliably. A single large malloc can fail with MemoryError (exit code 1)
    # instead of triggering OOMKilled, depending on the host's overcommit settings.
    memory_limit = TypeAdapter(ByteSize).validate_python("50MiB")
    memory_exceeding_task = sidecar_task(
        service_key="python",
        service_version="3.11-slim",
        command=[
            "python",
            "-c",
            "import sys; blocks = [];\n"
            "while True:\n"
            "    blocks.append(bytearray(1024*1024))\n"
            "    print(f'Allocated {len(blocks)} MiB', flush=True)\n",
        ],
    )

    # Execute the task and expect a runtime error due to memory limit exceeded

    future = dask_client.submit(
        run_computational_sidecar,
        **memory_exceeding_task.sidecar_params(),
        resources={"RAM": memory_limit},
    )
    with pytest.raises(ServiceOutOfMemoryError):
        future.result()
