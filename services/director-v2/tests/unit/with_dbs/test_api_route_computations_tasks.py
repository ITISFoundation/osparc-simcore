# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any, Awaitable, Callable, NamedTuple
from unittest import mock

import httpx
import pytest
from faker import Faker
from fastapi import FastAPI, status
from models_library.api_schemas_directorv2.comp_tasks import TaskLogFileGet
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import parse_raw_as
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


def get_app(async_client: httpx.AsyncClient) -> FastAPI:
    # pylint: disable=protected-access
    app = async_client._transport.app  # type: ignore
    assert app
    assert isinstance(app, FastAPI)
    return app


@pytest.fixture
def mock_env(
    mock_env: EnvVarsDict,  # sets default env vars
    postgres_host_config,  # sets postgres env vars
    monkeypatch: pytest.MonkeyPatch,
):
    # overrides mock_env
    monkeypatch.setenv("S3_ENDPOINT", "endpoint")
    monkeypatch.setenv("S3_ACCESS_KEY", "access_key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret_key")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket_name")
    monkeypatch.setenv("S3_SECURE", "false")


@pytest.fixture
def client(async_client: httpx.AsyncClient, mocker) -> httpx.AsyncClient:
    # overrides client
    # WARNING: this is an httpx.AsyncClient and not a TestClient!!
    app = get_app(async_client)

    settings: AppSettings = app.state.settings
    assert settings
    print(settings.json(indent=1))

    return async_client


@pytest.fixture
def mocked_nodeports_storage_client(mocker, faker: Faker) -> dict[str, mock.MagicMock]:
    # NOTE: mocking storage API would require aioresponses since the access to storage
    # is via node-ports which uses aiohttp-client! In order to avoid adding an extra
    # dependency we will patch storage-client functions in simcore-sdk's nodeports

    class Loc(NamedTuple):
        name: str
        id: int

    return {
        "get_download_file_link": mocker.patch(
            "simcore_sdk.node_ports_common.storage_client.get_download_file_link",
            autospec=True,
            return_value=faker.url(),
        ),
        "get_storage_locations": mocker.patch(
            "simcore_sdk.node_ports_common.storage_client.get_storage_locations",
            autospec=True,
            return_value=[
                Loc(name="simcore.s3", id=0),
            ],
        ),
    }


@pytest.fixture
def user(registered_user: Callable[..., dict[str, Any]]):
    user = registered_user()
    return user


@pytest.fixture
def user_id(user):
    return user["id"]


@pytest.fixture
async def project_id(
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    user: dict[str, Any],
    project: Callable[..., Awaitable[ProjectAtDB]],
    pipeline: Callable[..., CompPipelineAtDB],
    tasks: Callable[..., list[CompTaskAtDB]],
):
    """project uuid of a saved project (w/ tasks up-to-date)"""

    # insert project -> db
    proj = await project(user, workbench=fake_workbench_without_outputs)

    # insert pipeline  -> comp_pipeline
    pipeline(
        project_id=proj.uuid,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    # insert tasks -> comp_tasks
    comp_tasks = tasks(user=user, project=proj)

    return proj.uuid


@pytest.fixture
def node_id(fake_workbench_adjacency: dict[str, Any]) -> NodeID:
    return NodeID(next(nid for nid in fake_workbench_adjacency.keys()))


# - tests api routes
#   - real postgres db with rows inserted in users, projects, comp_tasks and comp_pipelines
#   - mocks responses from storage API patching nodeports
#


async def test_get_all_tasks_log_files(
    mocked_nodeports_storage_client: dict[str, mock.MagicMock],
    client: httpx.AsyncClient,
    user_id: UserID,
    project_id: ProjectID,
):
    resp = await client.get(
        f"/v2/computations/{project_id}/tasks/-/logfile", params={"user_id": user_id}
    )

    # calls storage
    mocked_nodeports_storage_client["get_storage_locations"].assert_not_called()
    assert mocked_nodeports_storage_client["get_download_file_link"].called

    # test expected response according to OAS!
    assert resp.status_code == status.HTTP_200_OK
    log_files = parse_raw_as(list[TaskLogFileGet], resp.text)
    assert log_files
    assert all(l.download_link for l in log_files)


async def test_get_task_logs_file(
    mocked_nodeports_storage_client: dict[str, mock.MagicMock],
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    client: httpx.AsyncClient,
):
    resp = await client.get(
        f"/v2/computations/{project_id}/tasks/{node_id}/logfile",
        params={"user_id": user_id},
    )
    assert resp.status_code == status.HTTP_200_OK

    log_file = TaskLogFileGet.parse_raw(resp.text)
    assert log_file.download_link


@pytest.mark.xfail
async def test_get_task_logs(
    project_id: ProjectID, node_id: NodeID, client: httpx.AsyncClient
):
    resp = await client.get(f"/{project_id}/tasks/{node_id}/logs")
