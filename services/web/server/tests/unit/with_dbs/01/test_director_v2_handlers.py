# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import base64

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
from models_library.api_schemas_directorv2.encryption import JobEncryptionContextMetadata
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
from simcore_service_webserver.director_v2._client import DirectorV2RestClient
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
        assert data["pipeline_id"] == f"{project_id}", (
            f"received pipeline id: {data['pipeline_id']}, expected {project_id}"
        )


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
    rsp = await client.post(f"{url}", json={"subgraph": [faker.uuid4(), faker.uuid4(), faker.uuid4()]})
    data, error = await assert_status(
        rsp,
        status.HTTP_201_CREATED if user_role == UserRole.GUEST else expected.created,
    )

    if user_role != UserRole.ANONYMOUS:
        assert not error, f"error received: {error}"
    if data:
        assert "pipeline_id" in data
        assert data["pipeline_id"] == f"{project_id}", (
            f"received pipeline id: {data['pipeline_id']}, expected {project_id}"
        )


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_start_computation_with_encryption(
    director_v2_service_mock: AioResponsesMock,
    mocker: MockerFixture,
    client: TestClient,
    logged_user: LoggedUser,
    project_id: ProjectID,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    assert client.app

    # Spy on DirectorV2RestClient.start_computation to capture forwarded options
    original_start = DirectorV2RestClient.start_computation
    captured_options: list[dict] = []

    async def _spy_start(self, project_id_, user_id, product_name, product_api_base_url, **options):
        captured_options.append(options)
        return await original_start(self, project_id_, user_id, product_name, product_api_base_url, **options)

    mocker.patch.object(DirectorV2RestClient, "start_computation", new=_spy_start)

    root_key = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode("ascii")
    node_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    encryption_body = {
        "root_key": root_key,
        "input_port_to_file_id": {node_id: {"input_1": "input_1"}},
    }

    url = client.app.router["start_computation"].url_for(project_id=f"{project_id}")
    rsp = await client.post(f"{url}", json={"encryption": encryption_body})
    data, error = await assert_status(
        rsp,
        status.HTTP_201_CREATED if user_role == UserRole.GUEST else expected.created,
    )

    if user_role != UserRole.ANONYMOUS:
        assert not error, f"error received: {error}"
    if data:
        assert "pipeline_id" in data
        assert data["pipeline_id"] == f"{project_id}"

    # Verify encryption was forwarded to director-v2
    if user_role not in {UserRole.ANONYMOUS}:
        assert len(captured_options) == 1
        forwarded = captured_options[0]
        assert "encryption" in forwarded
        assert isinstance(forwarded["encryption"], JobEncryptionContextMetadata)
        assert forwarded["encryption"].root_key.get_secret_value() == root_key


@pytest.mark.parametrize(*standard_role_response(), ids=str)
@pytest.mark.parametrize(
    "invalid_encryption_body, expected_error_fragment",
    [
        pytest.param(
            {"root_key": "not-valid-base64!!!", "input_port_to_file_id": {}},
            "root_key must be valid base64",
            id="non_base64_root_key",
        ),
        pytest.param(
            {
                "root_key": base64.b64encode(b"tooshort").decode("ascii"),
                "input_port_to_file_id": {},
            },
            "root_key must decode to 32 bytes",
            id="root_key_wrong_size",
        ),
        pytest.param(
            {"input_port_to_file_id": {}},
            "root_key",
            id="missing_root_key",
        ),
        pytest.param(
            {
                "root_key": base64.b64encode(b"0123456789abcdef0123456789abcdef").decode("ascii"),
                "input_port_to_file_id": {"not-a-uuid": {"input_1": "input_1"}},
            },
            "input_port_to_file_id",
            id="invalid_node_id_in_input_port_map",
        ),
    ],
)
async def test_start_computation_with_invalid_encryption(
    director_v2_service_mock: AioResponsesMock,
    client: TestClient,
    logged_user: LoggedUser,
    project_id: ProjectID,
    user_role: UserRole,
    expected: ExpectedResponse,
    invalid_encryption_body: dict,
    expected_error_fragment: str,
):
    assert client.app

    url = client.app.router["start_computation"].url_for(project_id=f"{project_id}")
    rsp = await client.post(f"{url}", json={"encryption": invalid_encryption_body})
    _, error = await assert_status(
        rsp, status.HTTP_422_UNPROCESSABLE_ENTITY if user_role == UserRole.GUEST else expected.unprocessable
    )
    if user_role not in {UserRole.ANONYMOUS}:
        assert expected_error_fragment in str(error)


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
    await assert_status(rsp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok)


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
        (status.HTTP_204_NO_CONTENT if user_role == UserRole.GUEST else expected.no_content),
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
    data, _ = await assert_status(resp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok)
    if user_role != UserRole.ANONYMOUS:
        assert ComputationRunRestGet.model_validate(data[0])
        assert data[0]["rootProjectName"] == user_project["name"]

    url = client.app.router["list_computation_iterations"].url_for(project_id=f"{user_project['uuid']}")
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok)
    if user_role != UserRole.ANONYMOUS:
        assert ComputationRunRestGet.model_validate(data[0])
        assert len(data) == 2
        assert data[0]["rootProjectName"] == user_project["name"]
        assert data[1]["rootProjectName"] == user_project["name"]

    url = client.app.router["list_computations_latest_iteration_tasks"].url_for(project_id=f"{user_project['uuid']}")
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok)
    if user_role != UserRole.ANONYMOUS:
        assert ComputationTaskRestGet.model_validate(data[0])


@pytest.fixture
def mock_rpc_list_computation_collection_runs_page(
    mocker: MockerFixture,
    user_project: ProjectDict,
) -> ComputationCollectionRunRpcGetPage:
    project_uuid = user_project["uuid"]
    example = ComputationCollectionRunRpcGet.model_config["json_schema_extra"]["examples"][0]
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
    example = ComputationCollectionRunTaskRpcGet.model_config["json_schema_extra"]["examples"][0]
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
    data, _ = await assert_status(resp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok)
    if user_role != UserRole.ANONYMOUS:
        assert ComputationCollectionRunRestGet.model_validate(data[0])
        assert data[0]["name"] == user_project["name"]

    url = client.app.router["list_computation_collection_run_tasks"].url_for(collection_run_id=faker.uuid4())
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok)
    if user_role != UserRole.ANONYMOUS:
        assert ComputationCollectionRunTaskRestGet.model_validate(data[0])
        assert len(data) == 1
        assert (
            data[0]["name"] == user_project["workbench"][mock_rpc_list_computation_collection_run_tasks_page]["label"]
        )


@pytest.fixture
async def populated_comp_run_collection(
    client: TestClient,
    postgres_db: sa.engine.Engine,
):
    assert client.app
    example = ComputationCollectionRunRpcGet.model_config["json_schema_extra"]["examples"][0]
    collection_run_id = example["collection_run_id"]

    with postgres_db.connect() as con:
        con.execute(
            comp_runs_collections.insert()
            .values(
                collection_run_id=collection_run_id,
                client_or_system_generated_id=collection_run_id,
                client_or_system_generated_display_name="My Collection Run",
                is_generated_by_system=False,
                created=sa.func.now(),  # pylint: disable=not-callable
                modified=sa.func.now(),  # pylint: disable=not-callable
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
    data, _ = await assert_status(resp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok)
    if user_role != UserRole.ANONYMOUS:
        assert ComputationCollectionRunRestGet.model_validate(data[0])
        assert data[0]["name"] == "My Collection Run"


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_list_computation_collection_runs_with_filter_only_running(
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
    query_parameters = {"filter_only_running": "true"}
    url_with_query = url.with_query(**query_parameters)
    resp = await client.get(f"{url_with_query}")
    data, _ = await assert_status(resp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok)
    if user_role != UserRole.ANONYMOUS:
        assert ComputationCollectionRunRestGet.model_validate(data[0])


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_list_computation_collection_runs_with_filter_root_project(
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
    query_parameters = {"filter_by_root_project_id": user_project["uuid"]}
    url_with_query = url.with_query(**query_parameters)
    resp = await client.get(f"{url_with_query}")
    data, _ = await assert_status(resp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok)
    if user_role != UserRole.ANONYMOUS:
        assert ComputationCollectionRunRestGet.model_validate(data[0])


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
        con.execute(projects_metadata.insert().values(project_uuid=project_uuid, custom={"job_name": "My Job Name"}))
        yield
        con.execute(projects_metadata.delete())


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_list_computation_collection_runs_tasks_with_different_names(
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
    url = client.app.router["list_computation_collection_run_tasks"].url_for(collection_run_id=faker.uuid4())
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok)
    if user_role != UserRole.ANONYMOUS:
        assert ComputationCollectionRunTaskRestGet.model_validate(data[0])
        assert data[0]["name"] == "My Job Name"
