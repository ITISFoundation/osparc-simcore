# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import datetime
import json
import re
import urllib.parse
from pathlib import Path
from random import choice
from typing import Any, Awaitable, Callable, Iterator

import httpx
import pytest
import respx
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_directorv2.comp_tasks import (
    ComputationCreate,
    ComputationGet,
)
from models_library.api_schemas_directorv2.services import ServiceExtras
from models_library.basic_types import VersionStr
from models_library.clusters import DEFAULT_CLUSTER_ID, Cluster, ClusterID
from models_library.projects import ProjectAtDB
from models_library.projects_nodes import NodeID, NodeState
from models_library.projects_pipeline import PipelineDetails
from models_library.projects_state import RunningState
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services import ServiceDockerData
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyHttpUrl, ValidationError, parse_obj_as
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_tasks import NodeClass
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB
from starlette import status

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture()
def mocked_rabbit_mq_client(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_director_v2.core.application.rabbitmq.RabbitMQClient",
        autospec=True,
    )


@pytest.fixture()
def minimal_configuration(
    mock_env: EnvVarsDict,
    postgres_host_config: dict[str, str],
    rabbit_service: RabbitSettings,
    monkeypatch: pytest.MonkeyPatch,
    mocked_rabbit_mq_client: None,
):
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SIDECAR_ENABLED", "false")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED", "1")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_ENABLED", "1")
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
    monkeypatch.setenv("S3_ENDPOINT", "endpoint")
    monkeypatch.setenv("S3_ACCESS_KEY", "access_key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret_key")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket_name")
    monkeypatch.setenv("S3_SECURE", "false")


@pytest.fixture(scope="session")
def fake_service_details(mocks_dir: Path) -> ServiceDockerData:
    fake_service_path = mocks_dir / "fake_service.json"
    assert fake_service_path.exists()
    fake_service_data = json.loads(fake_service_path.read_text())
    return ServiceDockerData(**fake_service_data)


@pytest.fixture
def fake_service_extras() -> ServiceExtras:
    extra_example = ServiceExtras.Config.schema_extra["examples"][2]
    random_extras = ServiceExtras(**extra_example)
    assert random_extras is not None
    return random_extras


@pytest.fixture
def fake_service_resources() -> ServiceResourcesDict:
    service_resources = parse_obj_as(
        ServiceResourcesDict,
        ServiceResourcesDictHelpers.Config.schema_extra["examples"][0],
    )
    return service_resources


@pytest.fixture
def fake_service_labels() -> dict[str, Any]:
    return choice(SimcoreServiceLabels.Config.schema_extra["examples"])


@pytest.fixture
def mocked_director_service_fcts(
    minimal_app: FastAPI,
    fake_service_details: ServiceDockerData,
    fake_service_extras: ServiceExtras,
    fake_service_labels: dict[str, Any],
) -> Iterator[respx.MockRouter]:
    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=minimal_app.state.settings.DIRECTOR_V0.endpoint,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        assert VersionStr.regex
        respx_mock.get(
            re.compile(
                r"/services/simcore%2Fservices%2F(comp|dynamic|frontend)%2F[^/]+/\d+.\d+.\d+$"
            ),
            name="get_service",
        ).respond(json={"data": [fake_service_details.dict(by_alias=True)]})
        respx_mock.get(
            re.compile(
                r"/services/simcore%2Fservices%2F(comp|dynamic|frontend)%2F[^/]+/\d+.\d+.\d+/labels"
            ),
            name="get_service_labels",
        ).respond(json={"data": fake_service_labels})

        respx_mock.get(
            re.compile(
                r"/service_extras/(simcore)%2F(services)%2F(comp|dynamic|frontend)%2F.+/(.+)"
            ),
            name="get_service_extras",
        ).respond(json={"data": fake_service_extras.dict(by_alias=True)})

        yield respx_mock


@pytest.fixture
def mocked_catalog_service_fcts(
    minimal_app: FastAPI,
    fake_service_details: ServiceDockerData,
    fake_service_resources: ServiceResourcesDict,
) -> Iterator[respx.MockRouter]:
    def _mocked_service_resources(request) -> httpx.Response:
        return httpx.Response(
            200, json=jsonable_encoder(fake_service_resources, by_alias=True)
        )

    def _mocked_services_details(
        request, service_key: str, service_version: str
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=jsonable_encoder(
                fake_service_details.copy(
                    update={
                        "key": urllib.parse.unquote(service_key),
                        "version": service_version,
                    }
                ),
                by_alias=True,
            ),
        )

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=minimal_app.state.settings.DIRECTOR_V2_CATALOG.api_base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.get(
            re.compile(
                r"services/(simcore)%2F(services)%2F(comp|dynamic|frontend)%2F[^/]+/[^\.]+.[^\.]+.[^\/]+/resources"
            ),
            name="get_service_resources",
        ).mock(side_effect=_mocked_service_resources)
        respx_mock.get(
            re.compile(
                r"services/(?P<service_key>simcore%2Fservices%2F(comp|dynamic|frontend)%2F[^/]+)/(?P<service_version>[^\.]+.[^\.]+.[^/\?]+).*"
            ),
            name="get_service",
        ).mock(side_effect=_mocked_services_details)

        yield respx_mock


@pytest.fixture
def mocked_catalog_service_fcts_deprecated(
    minimal_app: FastAPI,
    fake_service_details: ServiceDockerData,
    fake_service_extras: ServiceExtras,
):
    def _mocked_services_details(
        request, service_key: str, service_version: str
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=jsonable_encoder(
                fake_service_details.copy(
                    update={
                        "key": urllib.parse.unquote(service_key),
                        "version": service_version,
                        "deprecated": (
                            datetime.datetime.now(tz=datetime.timezone.utc)
                            - datetime.timedelta(days=1)
                        ).isoformat(),
                    }
                ),
                by_alias=True,
            ),
        )

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=minimal_app.state.settings.DIRECTOR_V2_CATALOG.api_base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.get(
            re.compile(
                r"services/(?P<service_key>simcore%2Fservices%2F(comp|dynamic|frontend)%2F[^/]+)/(?P<service_version>[^\.]+.[^\.]+.[^/\?]+).*"
            ),
            name="get_service",
        ).mock(side_effect=_mocked_services_details)

        yield respx_mock


@pytest.fixture
def product_name(faker: Faker) -> str:
    return faker.name()


async def test_computation_create_validators(
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    fake_workbench_without_outputs: dict[str, Any],
    faker: Faker,
):
    user = registered_user()
    proj = await project(user, workbench=fake_workbench_without_outputs)
    # cluster id and use_on_demand raises
    with pytest.raises(ValidationError, match=r"cluster_id cannot be set.+"):
        ComputationCreate(
            user_id=user["id"],
            project_id=proj.uuid,
            product_name=faker.pystr(),
            use_on_demand_clusters=True,
            cluster_id=faker.pyint(),
        )
    # this should not raise
    ComputationCreate(
        user_id=user["id"],
        project_id=proj.uuid,
        product_name=faker.pystr(),
        use_on_demand_clusters=True,
        cluster_id=None,
    )
    ComputationCreate(
        user_id=user["id"],
        project_id=proj.uuid,
        product_name=faker.pystr(),
        use_on_demand_clusters=False,
        cluster_id=faker.pyint(),
    )
    ComputationCreate(
        user_id=user["id"],
        project_id=proj.uuid,
        product_name=faker.pystr(),
        use_on_demand_clusters=True,
    )
    ComputationCreate(
        user_id=user["id"],
        project_id=proj.uuid,
        product_name=faker.pystr(),
        use_on_demand_clusters=False,
    )


async def test_create_computation(
    minimal_configuration: None,
    mocked_director_service_fcts,
    mocked_catalog_service_fcts,
    product_name: str,
    fake_workbench_without_outputs: dict[str, Any],
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx.AsyncClient,
):
    user = registered_user()
    proj = await project(user, workbench=fake_workbench_without_outputs)
    create_computation_url = httpx.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"], project_id=proj.uuid, product_name=product_name
            )
        ),
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text


async def test_start_computation_without_product_fails(
    minimal_configuration: None,
    mocked_director_service_fcts,
    mocked_catalog_service_fcts,
    product_name: str,
    fake_workbench_without_outputs: dict[str, Any],
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx.AsyncClient,
):
    user = registered_user()
    proj = await project(user, workbench=fake_workbench_without_outputs)
    create_computation_url = httpx.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json={
            "user_id": f"{user['id']}",
            "project_id": f"{proj.uuid}",
            "start_pipeline": f"{True}",
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text


async def test_start_computation(
    minimal_configuration: None,
    mocked_director_service_fcts,
    mocked_catalog_service_fcts,
    product_name: str,
    fake_workbench_without_outputs: dict[str, Any],
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx.AsyncClient,
):
    user = registered_user()
    proj = await project(user, workbench=fake_workbench_without_outputs)
    create_computation_url = httpx.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                start_pipeline=True,
                product_name=product_name,
            )
        ),
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    mocked_get_service_resources = mocked_catalog_service_fcts["get_service_resources"]
    # there should be as many calls to the catalog as there are no defined resources by default
    assert mocked_get_service_resources.call_count == len(
        fake_workbench_without_outputs
    )


async def test_start_computation_with_project_node_resources_defined(
    minimal_configuration: None,
    mocked_director_service_fcts,
    mocked_catalog_service_fcts,
    product_name: str,
    fake_workbench_without_outputs: dict[str, Any],
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx.AsyncClient,
):
    user = registered_user()
    proj = await project(
        user,
        project_nodes_overrides={
            "required_resources": ServiceResourcesDictHelpers.Config.schema_extra[
                "examples"
            ][0]
        },
        workbench=fake_workbench_without_outputs,
    )
    create_computation_url = httpx.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                start_pipeline=True,
                product_name=product_name,
            )
        ),
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    mocked_get_service_resources = mocked_catalog_service_fcts["get_service_resources"]
    # there should be no calls to the catalog as there are resources defined, so no need to call the catalog
    assert mocked_get_service_resources.call_count == 0


async def test_start_computation_with_deprecated_services_raises_406(
    minimal_configuration: None,
    mocked_director_service_fcts,
    mocked_catalog_service_fcts_deprecated,
    product_name: str,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx.AsyncClient,
):
    user = registered_user()
    proj = await project(user, workbench=fake_workbench_without_outputs)
    create_computation_url = httpx.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                start_pipeline=True,
                product_name=product_name,
            )
        ),
    )
    assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE, response.text


@pytest.fixture
def unusable_cluster(
    registered_user: Callable[..., dict[str, Any]],
    cluster: Callable[..., Cluster],
) -> ClusterID:
    user = registered_user()
    created_cluster = cluster(user)
    return created_cluster.id


async def test_start_computation_with_forbidden_cluster_raises_403(
    minimal_configuration: None,
    mocked_director_service_fcts,
    mocked_catalog_service_fcts,
    product_name: str,
    fake_workbench_without_outputs: dict[str, Any],
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx.AsyncClient,
    unusable_cluster: ClusterID,
):
    user = registered_user()
    proj = await project(user, workbench=fake_workbench_without_outputs)
    create_computation_url = httpx.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                start_pipeline=True,
                product_name=product_name,
                cluster_id=unusable_cluster,
            )
        ),
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN, response.text
    assert f"cluster {unusable_cluster}" in response.text


async def test_start_computation_with_unknown_cluster_raises_406(
    minimal_configuration: None,
    mocked_director_service_fcts,
    mocked_catalog_service_fcts,
    product_name: str,
    fake_workbench_without_outputs: dict[str, Any],
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx.AsyncClient,
    faker: Faker,
):
    user = registered_user()
    proj = await project(user, workbench=fake_workbench_without_outputs)
    create_computation_url = httpx.URL("/v2/computations")
    unknown_cluster_id = faker.pyint(1, 10000)
    response = await async_client.post(
        create_computation_url,
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                start_pipeline=True,
                product_name=product_name,
                cluster_id=unknown_cluster_id,
            )
        ),
    )
    assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE, response.text
    assert f"cluster {unknown_cluster_id}" in response.text


async def test_get_computation_from_empty_project(
    minimal_configuration: None,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    pipeline: Callable[..., CompPipelineAtDB],
    faker: Faker,
    async_client: httpx.AsyncClient,
):
    user = registered_user()
    get_computation_url = httpx.URL(
        f"/v2/computations/{faker.uuid4()}?user_id={user['id']}"
    )
    # the project exists but there is no pipeline yet
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    # create the project
    proj = await project(user, workbench=fake_workbench_without_outputs)
    get_computation_url = httpx.URL(
        f"/v2/computations/{proj.uuid}?user_id={user['id']}"
    )
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    # create an empty pipeline
    pipeline(
        project_id=proj.uuid,
    )
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_200_OK, response.text
    returned_computation = ComputationGet.parse_obj(response.json())
    assert returned_computation
    expected_computation = ComputationGet(
        id=proj.uuid,
        state=RunningState.UNKNOWN,
        pipeline_details=PipelineDetails(
            adjacency_list={}, node_states={}, progress=None
        ),
        url=parse_obj_as(
            AnyHttpUrl, f"{async_client.base_url.join(get_computation_url)}"
        ),
        stop_url=None,
        result=None,
        iteration=None,
        cluster_id=None,
        started=None,
        stopped=None,
        submitted=None,
    )
    assert returned_computation.dict() == expected_computation.dict()


async def test_get_computation_from_not_started_computation_task(
    minimal_configuration: None,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    pipeline: Callable[..., CompPipelineAtDB],
    tasks: Callable[..., list[CompTaskAtDB]],
    async_client: httpx.AsyncClient,
):
    user = registered_user()
    proj = await project(user, workbench=fake_workbench_without_outputs)
    get_computation_url = httpx.URL(
        f"/v2/computations/{proj.uuid}?user_id={user['id']}"
    )
    pipeline(
        project_id=proj.uuid,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    # create no task this should trigger an exception
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_409_CONFLICT, response.text

    # now create the expected tasks and the state is good again
    comp_tasks = tasks(user=user, project=proj)
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_200_OK, response.text
    returned_computation = ComputationGet.parse_obj(response.json())
    assert returned_computation
    expected_computation = ComputationGet(
        id=proj.uuid,
        state=RunningState.NOT_STARTED,
        pipeline_details=PipelineDetails(
            adjacency_list=parse_obj_as(
                dict[NodeID, list[NodeID]], fake_workbench_adjacency
            ),
            progress=0,
            node_states={
                t.node_id: NodeState(
                    modified=True,
                    currentStatus=RunningState.NOT_STARTED,
                    progress=None,
                    dependencies={
                        NodeID(node)
                        for node, next_nodes in fake_workbench_adjacency.items()
                        if f"{t.node_id}" in next_nodes
                    },
                )
                for t in comp_tasks
                if t.node_class == NodeClass.COMPUTATIONAL
            },
        ),
        url=parse_obj_as(
            AnyHttpUrl, f"{async_client.base_url.join(get_computation_url)}"
        ),
        stop_url=None,
        result=None,
        iteration=None,
        cluster_id=None,
        started=None,
        stopped=None,
        submitted=None,
    )
    _CHANGED_FIELDS = {"submitted"}
    assert returned_computation.dict(
        exclude=_CHANGED_FIELDS
    ) == expected_computation.dict(exclude=_CHANGED_FIELDS)
    assert returned_computation.dict(
        include=_CHANGED_FIELDS
    ) != expected_computation.dict(include=_CHANGED_FIELDS)


async def test_get_computation_from_published_computation_task(
    minimal_configuration: None,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    pipeline: Callable[..., CompPipelineAtDB],
    tasks: Callable[..., list[CompTaskAtDB]],
    runs: Callable[..., CompRunsAtDB],
    async_client: httpx.AsyncClient,
):
    user = registered_user()
    proj = await project(user, workbench=fake_workbench_without_outputs)
    pipeline(
        project_id=proj.uuid,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    comp_tasks = tasks(user=user, project=proj, state=StateType.PUBLISHED, progress=0)
    comp_runs = runs(user=user, project=proj, result=StateType.PUBLISHED)
    assert comp_runs
    get_computation_url = httpx.URL(
        f"/v2/computations/{proj.uuid}?user_id={user['id']}"
    )
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_200_OK, response.text
    returned_computation = ComputationGet.parse_obj(response.json())
    assert returned_computation
    expected_stop_url = async_client.base_url.join(
        f"/v2/computations/{proj.uuid}:stop?user_id={user['id']}"
    )
    expected_computation = ComputationGet(
        id=proj.uuid,
        state=RunningState.PUBLISHED,
        pipeline_details=PipelineDetails(
            adjacency_list=parse_obj_as(
                dict[NodeID, list[NodeID]], fake_workbench_adjacency
            ),
            node_states={
                t.node_id: NodeState(
                    modified=True,
                    currentStatus=RunningState.PUBLISHED,
                    dependencies={
                        NodeID(node)
                        for node, next_nodes in fake_workbench_adjacency.items()
                        if f"{t.node_id}" in next_nodes
                    },
                    progress=0,
                )
                for t in comp_tasks
                if t.node_class == NodeClass.COMPUTATIONAL
            },
            progress=0,
        ),
        url=parse_obj_as(
            AnyHttpUrl, f"{async_client.base_url.join(get_computation_url)}"
        ),
        stop_url=parse_obj_as(AnyHttpUrl, f"{expected_stop_url}"),
        result=None,
        iteration=1,
        cluster_id=DEFAULT_CLUSTER_ID,
        started=None,
        stopped=None,
        submitted=None,
    )

    _CHANGED_FIELDS = {"submitted"}
    assert returned_computation.dict(
        exclude=_CHANGED_FIELDS
    ) == expected_computation.dict(exclude=_CHANGED_FIELDS)
    assert returned_computation.dict(
        include=_CHANGED_FIELDS
    ) != expected_computation.dict(include=_CHANGED_FIELDS)
