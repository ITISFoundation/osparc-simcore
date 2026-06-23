# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member
# pylint: disable=too-many-arguments

import re
from pprint import pformat
from unittest import mock

import distributed
import fsspec
import pytest
from dask_task_models_library.container_tasks.io import FileUrl, TaskOutputData
from models_library.services_resources import BootMode
from pytest_simcore.helpers.dask_sidecar_tasks import (
    ServiceExampleParam,
    assert_expected_logs_published_to_rabbit,
    assert_parse_progresses_from_progress_event_handler,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.s3 import S3Settings
from simcore_service_dask_sidecar.utils.files import (
    _s3fs_settings_from_s3_settings,
)
from simcore_service_dask_sidecar.worker import run_computational_sidecar

pytest_simcore_core_services_selection = [
    "rabbit",
]


def test_run_computational_sidecar_real_fct(
    caplog_info_level: pytest.LogCaptureFixture,
    app_environment: EnvVarsDict,
    dask_subsystem_mock: dict[str, mock.Mock],
    sleeper_task: ServiceExampleParam,
    mocked_get_image_labels: mock.Mock,
    s3_settings: S3Settings,
    log_rabbit_client_parser: mock.AsyncMock,
):
    output_data = run_computational_sidecar(
        **sleeper_task.sidecar_params(),
    )
    mocked_get_image_labels.assert_called_once_with(
        mock.ANY,
        sleeper_task.docker_basic_auth,
        sleeper_task.service_key,
        sleeper_task.service_version,
    )
    assert log_rabbit_client_parser.called

    # check that the task produces expected logs
    for log in sleeper_task.expected_logs:
        r = re.compile(rf"\[{sleeper_task.service_key}:{sleeper_task.service_version} - .+\/.+\]: ({log})")
        search_results = list(filter(r.search, caplog_info_level.messages))
        assert len(search_results) > 0, (
            f"Could not find '{log}' in worker_logs:\n {pformat(caplog_info_level.messages, width=240)}"
        )
    for log in sleeper_task.expected_logs:
        assert re.search(
            rf"\[{sleeper_task.service_key}:{sleeper_task.service_version} - .+\/.+\]: ({log})",
            caplog_info_level.text,
        )
    # check that the task produce the expected data, not less not more
    for k, v in sleeper_task.expected_output_data.items():
        assert k in output_data
        assert output_data[k] == v

    s3_storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)

    for k, v in output_data.items():
        assert k in sleeper_task.expected_output_data
        assert v == sleeper_task.expected_output_data[k]

        # if there are file urls in the output, check they exist
        if isinstance(v, FileUrl):
            with fsspec.open(f"{v.url}", **s3_storage_kwargs) as fp:
                assert fp.details.get("size") > 0  # type: ignore

    # check the task has created a log file
    with fsspec.open(f"{sleeper_task.log_file_url}", mode="rt", **s3_storage_kwargs) as fp:
        saved_logs = fp.read()  # type: ignore
    assert saved_logs
    for log in sleeper_task.expected_logs:
        assert log in saved_logs


@pytest.mark.parametrize("integration_version, boot_mode", [("1.0.0", BootMode.CPU)], indirect=True)
def test_run_multiple_computational_sidecar_dask(
    dask_client: distributed.Client,
    sleeper_task: ServiceExampleParam,
    mocked_get_image_labels: mock.Mock,
):
    NUMBER_OF_TASKS = 50

    futures = [
        dask_client.submit(
            run_computational_sidecar,
            **sleeper_task.sidecar_params(),
            resources={},
        )
        for _ in range(NUMBER_OF_TASKS)
    ]

    results = dask_client.gather(futures)
    assert results
    assert isinstance(results, list)
    # for result in results:
    # check that the task produce the expected data, not less not more
    for output_data in results:
        for k, v in sleeper_task.expected_output_data.items():
            assert k in output_data
            assert output_data[k] == v

    mocked_get_image_labels.assert_called()


@pytest.mark.parametrize("integration_version, boot_mode", [("1.0.0", BootMode.CPU)], indirect=True)
async def test_run_computational_sidecar_dask(
    app_environment: EnvVarsDict,
    sleeper_task: ServiceExampleParam,
    progress_event_handler: mock.Mock,
    mocked_get_image_labels: mock.Mock,
    s3_settings: S3Settings,
    log_rabbit_client_parser: mock.AsyncMock,
    dask_client: distributed.Client,
):
    future = dask_client.submit(
        run_computational_sidecar,
        **sleeper_task.sidecar_params(),
        resources={},
    )

    worker_name = next(iter(dask_client.scheduler_info()["workers"]))
    assert worker_name
    output_data = future.result()
    assert output_data
    assert isinstance(output_data, TaskOutputData)

    # check that the task produces expected logs
    assert_parse_progresses_from_progress_event_handler(progress_event_handler)

    await assert_expected_logs_published_to_rabbit(
        log_rabbit_client_parser,
        sleeper_task.expected_logs,
        match="prefix",
    )

    # check that the task produce the expected data, not less not more
    assert isinstance(output_data, TaskOutputData)
    for k, v in sleeper_task.expected_output_data.items():
        assert k in output_data
        assert output_data[k] == v

    s3_storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)
    for k, v in output_data.items():
        assert k in sleeper_task.expected_output_data
        assert v == sleeper_task.expected_output_data[k]

        # if there are file urls in the output, check they exist
        if isinstance(v, FileUrl):
            with fsspec.open(f"{v.url}", **s3_storage_kwargs) as fp:
                assert fp.details.get("size") > 0  # type: ignore
    mocked_get_image_labels.assert_called()
