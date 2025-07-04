# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_directorv2.comp_runs import (
    ComputationCollectionRunRpcGet,
    ComputationCollectionRunRpcGetPage,
    ComputationCollectionRunTaskRpcGet,
    ComputationCollectionRunTaskRpcGetPage,
    ComputationRunRpcGet,
    ComputationRunRpcGetPage,
    ComputationTaskRpcGet,
    ComputationTaskRpcGetPage,
)
from models_library.api_schemas_webserver.computations import (
    ComputationCollectionRunRestGet,
    ComputationCollectionRunTaskRestGet,
    ComputationRunRestGet,
    ComputationTaskRestGet,
)
from models_library.projects import ProjectID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import LoggedUser
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
)
from pytest_simcore.services_api_mocks_for_aiohttp_clients import AioResponsesMock
from servicelib.aiohttp import status
from simcore_postgres_database.models.comp_runs_collections import comp_runs_collections
from simcore_postgres_database.models.projects_metadata import projects_metadata
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return ProjectID(faker.uuid4())


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_start_computation(
    director_v2_service_mock: AioResponsesMock,
    client: TestClient,
    logged_user: LoggedUser,
    project_id: ProjectID,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    assert client.app

    url = client.app.router["start_computation"].url_for(project_id=f"{project_id}")
    rsp = await client.post(f"{url}")
    data, error = await assert_status(
        rsp,
        status.HTTP_201_CREATED if user_role == UserRole.GUEST else expected.created,
    )

    if user_role != UserRole.ANONYMOUS:
        assert not error, f"error received: {error}"
    if data:
        assert "pipeline_id" in data
        assert (
            data["pipeline_id"] == f"{project_id}"
        ), f"received pipeline id: {data['pipeline_id']}, expected {project_id}"


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_start_partial_computation(
    director_v2_service_mock: AioResponsesMock,
    client: TestClient,
    logged_user: LoggedUser,
    project_id: ProjectID,
    user_role: UserRole,
    expected: ExpectedResponse,
    faker: Faker,
):
    assert client.app

    url = client.app.router["start_computation"].url_for(project_id=f"{project_id}")
    rsp = await client.post(
        f"{url}", json={"subgraph": [faker.uuid4(), faker.uuid4(), faker.uuid4()]}
    )
    data, error = await assert_status(
        rsp,
        status.HTTP_201_CREATED if user_role == UserRole.GUEST else expected.created,
    )

    if user_role != UserRole.ANONYMOUS:
        assert not error, f"error received: {error}"
    if data:
        assert "pipeline_id" in data
        assert (
            data["pipeline_id"] == f"{project_id}"
        ), f"received pipeline id: {data['pipeline_id']}, expected {project_id}"


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_get_computation(
    director_v2_service_mock: AioResponsesMock,
    client: TestClient,
    logged_user: LoggedUser,
    project_id: ProjectID,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    assert client.app
    url = client.app.router["get_computation"].url_for(project_id=f"{project_id}")
    rsp = await client.get(f"{url}")
    await assert_status(
        rsp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok
    )


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_stop_computation(
    director_v2_service_mock: AioResponsesMock,
    client: TestClient,
    logged_user: LoggedUser,
    project_id: ProjectID,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    assert client.app
    url = client.app.router["stop_computation"].url_for(project_id=f"{project_id}")
    rsp = await client.post(f"{url}")
    await assert_status(
        rsp,
        (
            status.HTTP_204_NO_CONTENT
            if user_role == UserRole.GUEST
            else expected.no_content
        ),
    )


@pytest.fixture
def mock_rpc_list_computations_latest_iteration_tasks(
    mocker: MockerFixture,
    user_project: ProjectDict,
) -> ComputationRunRpcGetPage:
    project_uuid = user_project["uuid"]
    example = ComputationRunRpcGet.model_config["json_schema_extra"]["examples"][0]
    example["project_uuid"] = project_uuid
    example["info"]["project_metadata"]["root_parent_project_id"] = project_uuid

    return mocker.patch(
        "simcore_service_webserver.director_v2._computations_service.computations.list_computations_latest_iteration_page",
        spec=True,
        return_value=ComputationRunRpcGetPage(
            items=[ComputationRunRpcGet.model_validate(example)],
            total=1,
        ),
    )


@pytest.fixture
def mock_rpc_list_computation_iterations(
    mocker: MockerFixture,
    user_project: ProjectDict,
) -> ComputationRunRpcGetPage:
    project_uuid = user_project["uuid"]
    example_1 = ComputationRunRpcGet.model_config["json_schema_extra"]["examples"][0]
    example_1["project_uuid"] = project_uuid
    example_2 = ComputationRunRpcGet.model_config["json_schema_extra"]["examples"][0]
    example_2["project_uuid"] = project_uuid
    example_2["iteration"] = 2

    return mocker.patch(
        "simcore_service_webserver.director_v2._computations_service.computations.list_computations_iterations_page",
        spec=True,
        return_value=ComputationRunRpcGetPage(
            items=[
                ComputationRunRpcGet.model_validate(example_1),
                ComputationRunRpcGet.model_validate(example_2),
            ],
            total=2,
        ),
    )


@pytest.fixture
def mock_rpc_list_computations_latest_iteration_tasks_page(
    mocker: MockerFixture,
    user_project: ProjectDict,
) -> ComputationTaskRpcGetPage:
    project_uuid = user_project["uuid"]
    workbench_ids = list(user_project["workbench"].keys())
    example = ComputationTaskRpcGet.model_config["json_schema_extra"]["examples"][0]
    example["node_id"] = workbench_ids[0]
    example["project_uuid"] = project_uuid

    return mocker.patch(
        "simcore_service_webserver.director_v2._computations_service.computations.list_computations_latest_iteration_tasks_page",
        spec=True,
        return_value=ComputationTaskRpcGetPage(
            items=[ComputationTaskRpcGet.model_validate(example)],
            total=1,
        ),
    )


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_list_computations_latest_iteration(
    director_v2_service_mock: AioResponsesMock,
    user_project: ProjectDict,
    client: TestClient,
    logged_user: LoggedUser,
    user_role: UserRole,
    expected: ExpectedResponse,
    mock_rpc_list_computations_latest_iteration_tasks: None,
    mock_rpc_list_computations_latest_iteration_tasks_page: None,
    mock_rpc_list_computation_iterations: None,
):
    assert client.app
    url = client.app.router["list_computations_latest_iteration"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(
        resp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok
    )
    if user_role != UserRole.ANONYMOUS:
        assert ComputationRunRestGet.model_validate(data[0])
        assert data[0]["rootProjectName"] == user_project["name"]

    url = client.app.router["list_computation_iterations"].url_for(
        project_id=f"{user_project['uuid']}"
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(
        resp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok
    )
    if user_role != UserRole.ANONYMOUS:
        assert ComputationRunRestGet.model_validate(data[0])
        assert len(data) == 2
        assert data[0]["rootProjectName"] == user_project["name"]
        assert data[1]["rootProjectName"] == user_project["name"]

    url = client.app.router["list_computations_latest_iteration_tasks"].url_for(
        project_id=f"{user_project['uuid']}"
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(
        resp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok
    )
    if user_role != UserRole.ANONYMOUS:
        assert ComputationTaskRestGet.model_validate(data[0])


@pytest.fixture
def mock_rpc_list_computation_collection_runs_page(
    mocker: MockerFixture,
    user_project: ProjectDict,
) -> ComputationCollectionRunRpcGetPage:
    project_uuid = user_project["uuid"]
    example = ComputationCollectionRunRpcGet.model_config["json_schema_extra"][
        "examples"
    ][0]
    example["project_ids"] = [project_uuid]
    example["info"]["project_metadata"]["root_parent_project_id"] = project_uuid

    return mocker.patch(
        "simcore_service_webserver.director_v2._computations_service.computations.list_computation_collection_runs_page",
        spec=True,
        return_value=ComputationCollectionRunRpcGetPage(
            items=[ComputationCollectionRunRpcGet.model_validate(example)],
            total=1,
        ),
    )


@pytest.fixture
def mock_rpc_list_computation_collection_run_tasks_page(
    mocker: MockerFixture,
    user_project: ProjectDict,
) -> str:
    project_uuid = user_project["uuid"]
    workbench_ids = list(user_project["workbench"].keys())
    example = ComputationCollectionRunTaskRpcGet.model_config["json_schema_extra"][
        "examples"
    ][0]
    example["node_id"] = workbench_ids[0]
    example["project_uuid"] = project_uuid

    mocker.patch(
        "simcore_service_webserver.director_v2._computations_service.computations.list_computation_collection_run_tasks_page",
        spec=True,
        return_value=ComputationCollectionRunTaskRpcGetPage(
            items=[ComputationCollectionRunTaskRpcGet.model_validate(example)],
            total=1,
        ),
    )

    return workbench_ids[0]


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_list_computation_collection_runs_and_tasks(
    director_v2_service_mock: AioResponsesMock,
    user_project: ProjectDict,
    client: TestClient,
    logged_user: LoggedUser,
    user_role: UserRole,
    expected: ExpectedResponse,
    mock_rpc_list_computation_collection_runs_page: None,
    mock_rpc_list_computation_collection_run_tasks_page: str,
    faker: Faker,
):
    assert client.app
    url = client.app.router["list_computation_collection_runs"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(
        resp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok
    )
    if user_role != UserRole.ANONYMOUS:
        assert ComputationCollectionRunRestGet.model_validate(data[0])
        assert data[0]["name"] == user_project["name"]

    url = client.app.router["list_computation_collection_run_tasks"].url_for(
        collection_run_id=faker.uuid4()
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(
        resp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok
    )
    if user_role != UserRole.ANONYMOUS:
        assert ComputationCollectionRunTaskRestGet.model_validate(data[0])
        assert len(data) == 1
        assert (
            data[0]["name"]
            == user_project["workbench"][
                mock_rpc_list_computation_collection_run_tasks_page
            ]["label"]
        )


@pytest.fixture
async def populated_comp_run_collection(
    client: TestClient,
    postgres_db: sa.engine.Engine,
):
    assert client.app
    example = ComputationCollectionRunRpcGet.model_config["json_schema_extra"][
        "examples"
    ][0]
    collection_run_id = example["collection_run_id"]

    with postgres_db.connect() as con:
        con.execute(
            comp_runs_collections.insert()
            .values(
                collection_run_id=collection_run_id,
                client_or_system_generated_id=collection_run_id,
                client_or_system_generated_display_name="My Collection Run",
                generated_by_system=False,
                created=sa.func.now(),
                modified=sa.func.now(),
            )
            .returning(comp_runs_collections.c.collection_run_id)
        )
        yield
        con.execute(comp_runs_collections.delete())


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_list_computation_collection_runs_with_client_defined_name(
    director_v2_service_mock: AioResponsesMock,
    user_project: ProjectDict,
    client: TestClient,
    logged_user: LoggedUser,
    user_role: UserRole,
    expected: ExpectedResponse,
    populated_comp_run_collection: None,
    mock_rpc_list_computation_collection_runs_page: None,
):
    assert client.app
    url = client.app.router["list_computation_collection_runs"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(
        resp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok
    )
    if user_role != UserRole.ANONYMOUS:
        assert ComputationCollectionRunRestGet.model_validate(data[0])
        assert data[0]["name"] == "My Collection Run"


@pytest.fixture
async def populated_project_metadata(
    client: TestClient,
    logged_user: LoggedUser,
    user_project: ProjectDict,
    postgres_db: sa.engine.Engine,
):
    assert client.app
    project_uuid = user_project["uuid"]
    with postgres_db.connect() as con:
        con.execute(
            projects_metadata.insert().values(
                **{
                    "project_uuid": project_uuid,
                    "custom": {"job_name": "My Job Name"},
                }
            )
        )
        yield
        con.execute(projects_metadata.delete())


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_list_computation_collection_runs_and_tasks_with_different_names(
    director_v2_service_mock: AioResponsesMock,
    user_project: ProjectDict,
    client: TestClient,
    logged_user: LoggedUser,
    user_role: UserRole,
    expected: ExpectedResponse,
    populated_project_metadata: None,
    mock_rpc_list_computation_collection_run_tasks_page: str,
    faker: Faker,
):
    assert client.app
    url = client.app.router["list_computation_collection_run_tasks"].url_for(
        collection_run_id=faker.uuid4()
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(
        resp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok
    )
    if user_role != UserRole.ANONYMOUS:
        assert ComputationCollectionRunTaskRestGet.model_validate(data[0])
        assert data[0]["name"] == "My Job Name"
