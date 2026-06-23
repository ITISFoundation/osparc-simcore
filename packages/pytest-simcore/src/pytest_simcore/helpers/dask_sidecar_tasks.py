"""Shared test data types and assertion helpers for the dask-sidecar computational task tests.

NOTE: kept service-agnostic on purpose (only depends on shared libraries) so it can be
imported reliably across test modules (pytest's ``prepend`` import mode makes cross-module
``conftest`` imports unreliable).
"""

import re
from dataclasses import dataclass
from pprint import pformat
from typing import Any, Literal
from unittest import mock

import pytest
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.events import TaskProgressEvent
from dask_task_models_library.container_tasks.io import (
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from dask_task_models_library.container_tasks.protocol import (
    ContainerTaskParameters,
    TaskOwner,
)
from models_library.basic_types import EnvVarKey
from models_library.rabbitmq_messages import LoggerRabbitMessage
from models_library.services_resources import BootMode
from packaging import version
from pydantic import AnyUrl
from settings_library.s3 import S3Settings
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

# shared parametrization reused by the many tests that run a single CPU task without a parent node
run_cpu_no_parent_node = pytest.mark.parametrize(
    "integration_version, boot_mode, task_owner",
    [("1.0.0", BootMode.CPU, "no_parent_node")],
    indirect=True,
)


@dataclass(slots=True, kw_only=True)
class ServiceExampleParam:
    docker_basic_auth: DockerBasicAuth
    service_key: str
    service_version: str
    command: list[str]
    input_data: TaskInputData
    output_data_keys: TaskOutputDataSchema
    log_file_url: AnyUrl
    expected_output_data: TaskOutputData
    expected_logs: list[str]
    integration_version: version.Version
    task_envs: dict[EnvVarKey, str]
    task_owner: TaskOwner
    boot_mode: BootMode
    s3_settings: S3Settings

    def sidecar_params(self) -> dict[str, Any]:
        return {
            "task_parameters": ContainerTaskParameters(
                image=self.service_key,
                tag=self.service_version,
                input_data=self.input_data,
                output_data_keys=self.output_data_keys,
                command=self.command,
                envs=self.task_envs,
                labels={},
                task_owner=self.task_owner,
                boot_mode=self.boot_mode,
            ),
            "docker_auth": self.docker_basic_auth,
            "log_file_url": self.log_file_url,
            "s3_settings": self.s3_settings,
        }


async def assert_expected_logs_published_to_rabbit(
    log_rabbit_client_parser: mock.AsyncMock,
    expected_logs: list[str],
    *,
    match: Literal["prefix", "contains"] = "prefix",
    expected_match_count: int | None = None,
) -> list[str]:
    """Polls the captured RabbitMQ log messages until every entry in ``expected_logs`` is found.

    Matching is done either by prefix-regex (``match="prefix"``) or by substring
    (``match="contains"``). When ``expected_match_count`` is provided, each expected entry must
    match exactly that many log lines (e.g. to assert no message is lost).

    Returns the collected worker logs.
    """
    worker_logs: list[str] = []
    async for attempt in AsyncRetrying(
        wait=wait_fixed(1),
        stop=stop_after_delay(60),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert log_rabbit_client_parser.called, "no logs were published to RabbitMQ during the computation"
            worker_logs = [
                message
                for msg in log_rabbit_client_parser.call_args_list
                for message in LoggerRabbitMessage.model_validate_json(msg.args[0]).messages
            ]
            for expected in expected_logs:
                if match == "prefix":
                    matches = [log for log in worker_logs if re.match(rf"^({expected}).*", log)]
                else:
                    matches = [log for log in worker_logs if expected in log]
                if expected_match_count is None:
                    assert matches, f"Could not find '{expected}' in worker logs:\n{pformat(worker_logs, width=240)}"
                else:
                    assert len(matches) == expected_match_count, (
                        f"Expected exactly {expected_match_count} matches of '{expected}' "
                        f"but found {len(matches)} in worker logs"
                    )
    return worker_logs


def assert_parse_progresses_from_progress_event_handler(
    progress_event_handler: mock.Mock,
) -> list[float]:
    assert progress_event_handler.called
    worker_progresses = [
        TaskProgressEvent.model_validate_json(msg.args[0][1]).progress for msg in progress_event_handler.call_args_list
    ]
    assert worker_progresses == sorted(set(worker_progresses)), "ordering of progress values incorrectly sorted!"
    assert worker_progresses[0] == 0, "missing/incorrect initial progress value"
    assert worker_progresses[-1] == 1, "missing/incorrect final progress value"
    return worker_progresses
