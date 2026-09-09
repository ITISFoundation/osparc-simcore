# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member
# pylint: disable=too-many-arguments

from collections.abc import Callable
from unittest import mock

import distributed
import pytest
from dask_task_models_library.container_tasks.errors import ServiceTimeoutLoggingError
from dask_task_models_library.container_tasks.io import TaskOutputData
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.dask_sidecar_tasks import (
    ServiceExampleParam,
    assert_expected_logs_published_to_rabbit,
    assert_parse_progresses_from_progress_event_handler,
    run_cpu_no_parent_node,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dask_sidecar.worker import run_computational_sidecar

pytest_simcore_core_services_selection = [
    "rabbit",
]


@run_cpu_no_parent_node
async def test_run_computational_sidecar_dask_does_not_lose_messages_with_pubsub(
    dask_client: distributed.Client,
    sidecar_task: Callable[..., ServiceExampleParam],
    progress_event_handler: mock.Mock,
    mocked_get_image_labels: mock.Mock,
    log_rabbit_client_parser: mock.AsyncMock,
):
    mocked_get_image_labels.assert_not_called()
    NUMBER_OF_LOGS = 20000
    future = dask_client.submit(
        run_computational_sidecar,
        **sidecar_task(
            command=[
                "/bin/bash",
                "-c",
                " && ".join(
                    [
                        f'N={NUMBER_OF_LOGS}; for ((i=1; i<=N; i++));do echo "This is iteration $i"; '
                        f'echo "progress: $i/{NUMBER_OF_LOGS}"; done '
                    ]
                ),
            ],
        ).sidecar_params(),
        resources={},
    )
    output_data = future.result()
    assert output_data is not None
    assert isinstance(output_data, TaskOutputData)

    # check that the task produces expected logs
    assert_parse_progresses_from_progress_event_handler(progress_event_handler)

    await assert_expected_logs_published_to_rabbit(
        log_rabbit_client_parser,
        ["This is iteration"],
        match="contains",
        expected_match_count=NUMBER_OF_LOGS,
    )
    mocked_get_image_labels.assert_called()


@run_cpu_no_parent_node
def test_delayed_logging_with_small_timeout_raises_exception(
    app_environment: EnvVarsDict,
    with_short_max_silence_timeout: EnvVarsDict,
    dask_subsystem_mock: dict[str, mock.Mock],
    sidecar_task: Callable[..., ServiceExampleParam],
    mocked_get_image_labels: mock.Mock,
):
    """https://github.com/aio-libs/aiodocker/issues/901"""

    # Configure the task to sleep first and then generate logs
    waiting_task = sidecar_task(
        command=[
            "/bin/bash",
            "-c",
            'echo "Starting task"; sleep 5; echo "After sleep"',
        ]
    )

    # Execute the task and expect a timeout exception in the logs
    with pytest.raises(ServiceTimeoutLoggingError):
        run_computational_sidecar(**waiting_task.sidecar_params())


@run_cpu_no_parent_node
def test_run_sidecar_with_managed_monitor_container_log_task_raising(
    app_environment: EnvVarsDict,
    dask_subsystem_mock: dict[str, mock.Mock],
    sidecar_task: Callable[..., ServiceExampleParam],
    mocked_get_image_labels: mock.Mock,
    mocker: MockerFixture,
):
    mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.core.managed_monitor_container_log_task",
        side_effect=RuntimeError("Simulated log monitoring failure"),
    )

    # Configure the task to sleep first and then generate logs
    waiting_task = sidecar_task(
        command=[
            "/bin/bash",
            "-c",
            'echo "Starting task"; sleep 5; echo "After sleep"',
        ]
    )

    # Execute the task and expect a timeout exception in the logs
    with pytest.raises(RuntimeError, match="Simulated log monitoring failure"):
        run_computational_sidecar(**waiting_task.sidecar_params())
