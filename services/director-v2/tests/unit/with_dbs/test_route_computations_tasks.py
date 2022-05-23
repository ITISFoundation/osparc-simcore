# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any, Callable, Iterator

import httpx
import pytest
import respx
from faker import Faker
from fastapi import FastAPI, status
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import parse_raw_as
from respx import MockRouter
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.domains.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.domains.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.models.schemas.comp_tasks import TaskLogFileGet

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
def mock_env(mock_env: None, monkeypatch: pytest.MonkeyPatch, postgres_host_config):
    # overrides mock_env
    monkeypatch.setenv("S3_ENDPOINT", "endpoint")
    monkeypatch.setenv("S3_ACCESS_KEY", "access_key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret_key")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket_name")
    monkeypatch.setenv("S3_SECURE", "false")


@pytest.fixture
def client(async_client: httpx.AsyncClient, mocker):
    # overrides client
    app = get_app(async_client)
    settings: AppSettings = app.state.settings
    assert settings
    print(settings.json(indent=1))
    return async_client


@pytest.fixture
def mocked_storage_service_api(
    client: httpx.AsyncClient, faker: Faker
) -> Iterator[MockRouter]:
    app = get_app(client)
    settings: AppSettings = app.state.settings

    assert settings
    assert settings.DIRECTOR_V2_STORAGE
    print(settings.DIRECTOR_V2_STORAGE.json(indent=1))

    # pylint: disable=not-context-manager
    with respx.mock(  # type: ignore
        base_url=settings.DIRECTOR_V2_STORAGE.endpoint,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        # TODO: sync with services/storage/src/simcore_service_storage/api/v0/openapi.yaml
        respx_mock.get(
            path__regex=r"/locations/(?P<location_id>\w+)/files/(?P<file_id>\w+)",
            name="download_file",
        ).respond(json={"data": {"link": faker.url()}})

        yield respx_mock


@pytest.fixture
def user(registered_user: Callable[..., dict[str, Any]]):
    user = registered_user()
    return user


@pytest.fixture
def user_id(user):
    return user["id"]


@pytest.fixture
def project_id(
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    user: dict[str, Any],
    project: Callable[..., ProjectAtDB],
    pipeline: Callable[..., CompPipelineAtDB],
    tasks: Callable[..., list[CompTaskAtDB]],
):
    """project uuid of a saved project (w/ tasks up-to-date)"""

    # insert project -> db
    proj = project(user, workbench=fake_workbench_without_outputs)

    # insert pipeline  -> comp_pipeline
    pipeline(
        project_id=proj.uuid,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    # insert tasks -> comp_tasks
    comp_tasks = tasks(user=user, project=proj)

    return proj.uuid


@pytest.fixture
def node_id(faker: Faker):
    return faker.uuid4()


#
# - tests api routes
#   - mocks responses from storage API
#


async def test_get_all_tasks_log_files(
    mocked_storage_service_api: MockRouter,
    client: httpx.AsyncClient,
    user_id: UserID,
    project_id: ProjectID,
):
    resp = await client.get(
        f"/v2/computations/{project_id}/tasks/-/logfile", params={"user_id": user_id}
    )

    # calls storage
    assert mocked_storage_service_api["download_file"].call_count == 1
    req: httpx.Request = mocked_storage_service_api["download_file"].calls[0].request
    assert f"{project_id}" in f"{req.url}"

    # test expected response according to OAS!
    assert resp.status_code == status.HTTP_200_OK
    log_files = parse_raw_as(list[TaskLogFileGet], resp.text)
    assert log_files
    assert all(l.download_link for l in log_files)


async def test_get_task_logs_file(
    user_id: UserID, project_id: ProjectID, node_id: NodeID, client: httpx.AsyncClient
):
    resp = await client.get(
        f"/v2/computations/{project_id}/tasks/{node_id}/logfile",
        params={"user_id": user_id},
    )
    assert resp.status_code == status.HTTP_200_OK

    log_file = TaskLogFileGet.parse_raw(resp.text)
    assert log_file.download_link


async def test_get_task_logs(
    project_id: ProjectID, node_id: NodeID, client: httpx.AsyncClient
):
    resp = await client.get(f"/{project_id}/tasks/{node_id}/logs")
