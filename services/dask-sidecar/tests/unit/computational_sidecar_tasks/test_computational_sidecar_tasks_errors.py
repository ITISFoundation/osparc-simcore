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
    # NOTE: We allocate dirty pages (written-to bytearrays) in 1MiB chunks up to a bounded
    # count, so the kernel memory-cgroup OOM killer fires reliably (untouched allocations
    # may not be committed, and a single large malloc can fail with MemoryError -> exit 1
    # depending on the host's overcommit settings). The bound also guarantees the
    # container terminates even if the OOM kill never happens, so the test fails with
    # service logs instead of hanging.
    # NOTE: the limit leaves headroom above the interpreter baseline so that the kernel
    # OOM kill (exit 137 / OOMKilled) dominates over Python raising MemoryError.
    memory_limit = TypeAdapter(ByteSize).validate_python("128MiB")
    memory_limit_mib = 128
    memory_exceeding_task = sidecar_task(
        service_key="python",
        service_version="3.11-slim",
        command=[
            "python",
            "-c",
            (
                "blocks = [];\n"
                f"for _ in range({4 * memory_limit_mib}):\n"
                "    blocks.append(bytearray(b'\\xff' * (1024*1024)))\n"
                "    print(f'Allocated {len(blocks)} MiB', flush=True)\n"
            ),
        ],
    )

    # Execute the task and expect an out-of-memory error due to the memory limit exceeded

    future = dask_client.submit(
        run_computational_sidecar,
        **memory_exceeding_task.sidecar_params(),
        resources={"RAM": memory_limit},
    )
    with pytest.raises(ServiceOutOfMemoryError):
        future.result(timeout=120)
