# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import os
from typing import Any, Callable

import pytest
from faker import Faker
from models_library.projects import ProjectAtDB
from models_library.projects_nodes_io import NodeID
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_director_v2.cli import DEFAULT_NODE_SAVE_RETRY, main
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
        "simcore_service_director_v2.cli.requires_dynamic_sidecar",
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


def test_project_save_state_ok(
    mock_requires_dynamic_sidecar: None,
    mock_save_service_state: None,
    cli_runner: CliRunner,
    project_at_db: ProjectAtDB,
):
    result = cli_runner.invoke(main, ["project-save-state", f"{project_at_db.uuid}"])
    print(result.stdout)
    assert result.exit_code == os.EX_OK, result.stdout
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
    assert result.exit_code == 1, result.stdout
    assert "The following nodes failed to save:" in result.stdout
    for node_uuid in project_at_db.workbench.keys():
        assert (
            result.stdout.count(f"Attempting to save {node_uuid}")
            == DEFAULT_NODE_SAVE_RETRY
        )
        assert result.stdout.count(f"- {node_uuid}") == 1
    assert result.stdout.endswith("Please try to save them individually!\n")


def test_node_save_state_ok(
    mock_requires_dynamic_sidecar: None,
    mock_save_service_state: None,
    project_at_db: ProjectAtDB,
    cli_runner: CliRunner,
    node_id: NodeID,
):
    result = cli_runner.invoke(main, ["node-save-state", f"{node_id}"])
    print(result.stdout)
    assert result.exit_code == os.EX_OK, result.stdout
    assert f"Node {node_id} save completed" in result.stdout


def test_node_save_state_retry_3_times_and_fails(
    mock_requires_dynamic_sidecar: None,
    mock_save_service_state_as_failing: None,
    project_at_db: ProjectAtDB,
    cli_runner: CliRunner,
    node_id: NodeID,
):
    result = cli_runner.invoke(main, ["node-save-state", f"{node_id}"])
    print(result.stdout)
    assert result.exit_code == 1, result.stdout
    assert f"Saving state for {node_id}" in result.stdout
    assert (
        result.stdout.count(f"Attempting to save {node_id}") == DEFAULT_NODE_SAVE_RETRY
    )
