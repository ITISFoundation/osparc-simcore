# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import os
import re
import traceback
from contextlib import asynccontextmanager
from typing import Any, AsyncIterable, AsyncIterator, Callable, Optional

import pytest
import respx
from click.testing import Result
from faker import Faker
from fastapi import status
from models_library.projects import ProjectAtDB
from models_library.projects_nodes_io import NodeID
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.long_running_tasks._models import ProgressCallback
from simcore_service_director_v2.cli import DEFAULT_NODE_SAVE_ATTEMPTS, main
from simcore_service_director_v2.cli._close_and_save_service import (
    ThinDV2LocalhostClient,
)
from simcore_service_director_v2.models.domains.dynamic_services import (
    DynamicServiceGet,
)
from simcore_service_director_v2.models.schemas.dynamic_services import (
    RunningDynamicServiceDetails,
)
from typer.testing import CliRunner

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture()
def minimal_configuration(
    mock_env: EnvVarsDict,
    postgres_host_config: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SIDECAR_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "1")
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
    monkeypatch.setenv("S3_ENDPOINT", "endpoint")
    monkeypatch.setenv("S3_ACCESS_KEY", "access_key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret_key")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket_name")
    monkeypatch.setenv("S3_SECURE", "false")


@pytest.fixture
def cli_runner(minimal_configuration: None) -> CliRunner:
    return CliRunner()


@pytest.fixture
def project_at_db(
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., ProjectAtDB],
    fake_workbench_without_outputs: dict[str, Any],
) -> ProjectAtDB:
    user = registered_user()
    return project(user, workbench=fake_workbench_without_outputs)


@pytest.fixture
def mock_requires_dynamic_sidecar(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_director_v2.cli._core.requires_dynamic_sidecar",
        spec=True,
    )


@pytest.fixture
def mock_save_service_state(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.api_client._public.DynamicSidecarClient.save_service_state",
        spec=True,
    )


@pytest.fixture
def mock_save_service_state_as_failing(mocker: MockerFixture) -> None:
    async def _always_raise(*args, **kwargs) -> None:
        raise Exception("I AM FAILING NOW")

    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.api_client._public.DynamicSidecarClient.save_service_state",
        side_effect=_always_raise,
    )


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def mock_get_node_state(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_director_v2.cli._core._get_dy_service_state",
        return_value=DynamicServiceGet.parse_obj(
            RunningDynamicServiceDetails.Config.schema_extra["examples"][0]
        ),
    )


@pytest.fixture
def task_id(faker: Faker) -> str:
    return f"tas_id.{faker.uuid4()}"


@pytest.fixture
async def mock_close_service_routes(
    mocker: MockerFixture, task_id: str
) -> AsyncIterable[None]:
    regex_base = r"/v2/dynamic_scheduler/services/([\w-]+)"
    with respx.mock(
        base_url=ThinDV2LocalhostClient.BASE_ADDRESS,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.patch(
            re.compile(f"{regex_base}/observation"), name="toggle_service_observation"
        ).respond(status_code=status.HTTP_204_NO_CONTENT)
        respx_mock.delete(
            re.compile(f"{regex_base}/containers"), name="delete_service_containers"
        ).respond(status_code=status.HTTP_202_ACCEPTED, json=task_id)
        respx_mock.post(
            re.compile(f"{regex_base}/state:save"), name="save_service_state"
        ).respond(status_code=status.HTTP_202_ACCEPTED, json=task_id)
        respx_mock.post(
            re.compile(f"{regex_base}/outputs:push"), name="push_service_outputs"
        ).respond(status_code=status.HTTP_202_ACCEPTED, json=task_id)
        respx_mock.delete(
            re.compile(f"{regex_base}/docker-resources"),
            name="delete_service_docker_resources",
        ).respond(status_code=status.HTTP_202_ACCEPTED, json=task_id)

        @asynccontextmanager
        async def _mocked_context_manger(
            client: Any,
            task_id: Any,
            *,
            task_timeout: Any,
            progress_callback: Optional[ProgressCallback] = None,
            status_poll_interval: Any = 5,
        ) -> AsyncIterator[None]:
            assert progress_callback
            await progress_callback("test", 1.0, task_id)
            yield

        mocker.patch(
            "simcore_service_director_v2.cli._close_and_save_service.periodic_task_result",
            side_effect=_mocked_context_manger,
        )

        yield


def _format_cli_error(result: Result) -> str:
    assert result.exception
    tb_message = "\n".join(traceback.format_tb(result.exception.__traceback__))
    return f"Below exception was raised by the cli:\n{tb_message}"


def test_project_save_state_ok(
    mock_requires_dynamic_sidecar: None,
    mock_save_service_state: None,
    cli_runner: CliRunner,
    project_at_db: ProjectAtDB,
):
    result = cli_runner.invoke(main, ["project-save-state", f"{project_at_db.uuid}"])
    print(result.stdout)
    assert result.exit_code == os.EX_OK, _format_cli_error(result)
    assert result.stdout.endswith(f"Save complete for project {project_at_db.uuid}\n")
    for node_uuid, node_content in project_at_db.workbench.items():
        assert f"Saving state for {node_uuid} {node_content.label}" in result.stdout

    assert f"Saving project '{project_at_db.uuid}' - '{project_at_db.name}'"


def test_project_save_state_retry_3_times_and_fails(
    mock_requires_dynamic_sidecar: None,
    mock_save_service_state_as_failing: None,
    cli_runner: CliRunner,
    project_at_db: ProjectAtDB,
):
    result = cli_runner.invoke(main, ["project-save-state", f"{project_at_db.uuid}"])
    print(result.stdout)
    assert result.exit_code == 1, _format_cli_error(result)
    assert "The following nodes failed to save:" in result.stdout
    for node_uuid in project_at_db.workbench.keys():
        assert (
            result.stdout.count(f"Attempting to save {node_uuid}")
            == DEFAULT_NODE_SAVE_ATTEMPTS
        )
        assert result.stdout.count(f"- {node_uuid}") == 1
    assert result.stdout.endswith("Please try to save them individually!\n")


def test_project_state(
    mock_get_node_state: None, project_at_db: ProjectAtDB, cli_runner: CliRunner
):
    result = cli_runner.invoke(
        main, ["project-state", f"{project_at_db.uuid}", "--no-blocking"]
    )
    assert result.exit_code == os.EX_OK, _format_cli_error(result)
    print(result.stdout)


def test_close_and_save_service(
    mock_close_service_routes: None, cli_runner: CliRunner, node_id: NodeID
):
    result = cli_runner.invoke(main, ["close-and-save-service", f"{node_id}"])
    assert result.exit_code == os.EX_OK, _format_cli_error(result)
    print(result.stdout)
