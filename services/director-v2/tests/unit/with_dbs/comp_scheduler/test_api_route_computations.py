# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint:disable=too-many-positional-arguments

import datetime as dt
import json
import re
import urllib.parse
from collections.abc import Awaitable, Callable, Iterator
from decimal import Decimal
from pathlib import Path
from random import choice
from typing import Any
from unittest import mock

import aiopg.sa
import httpx
import pytest
import respx
from faker import Faker
from fastapi import FastAPI, status
from models_library.api_schemas_catalog.services import ServiceGet
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceTypeGet
from models_library.api_schemas_directorv2.comp_tasks import (
    ComputationCreate,
    ComputationGet,
)
from models_library.api_schemas_directorv2.services import ServiceExtras
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingPlanGet,
    PricingUnitGet,
)
from models_library.clusters import DEFAULT_CLUSTER_ID, Cluster, ClusterID
from models_library.projects import ProjectAtDB
from models_library.projects_nodes import NodeID, NodeState
from models_library.projects_nodes_io import NodeIDStr
from models_library.projects_pipeline import PipelineDetails
from models_library.projects_state import RunningState
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services import ServiceMetaDataPublished
from models_library.services_resources import (
    DEFAULT_SINGLE_SERVICE_NAME,
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from models_library.wallets import WalletInfo
from pydantic import AnyHttpUrl, ByteSize, PositiveInt, TypeAdapter, ValidationError
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_tasks import NodeClass
from simcore_postgres_database.utils_projects_nodes import ProjectNodesRepo
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.modules.db.repositories.comp_tasks._utils import (
    _CPUS_SAFE_MARGIN,
    _RAM_SAFE_MARGIN_RATIO,
)
from simcore_service_director_v2.utils.computations import to_node_class

pytest_simcore_core_services_selection = ["postgres", "rabbit", "redis"]
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
    redis_service: RedisSettings,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
    with_disabled_auto_scheduling: mock.Mock,
    with_disabled_scheduler_publisher: mock.Mock,
):
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SIDECAR_ENABLED", "false")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED", "1")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_ENABLED", "1")
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
    monkeypatch.setenv("S3_ENDPOINT", faker.url())
    monkeypatch.setenv("S3_ACCESS_KEY", faker.pystr())
    monkeypatch.setenv("S3_REGION", faker.pystr())
    monkeypatch.setenv("S3_SECRET_KEY", faker.pystr())
    monkeypatch.setenv("S3_BUCKET_NAME", faker.pystr())


@pytest.fixture(scope="session")
def fake_service_details(mocks_dir: Path) -> ServiceMetaDataPublished:
    fake_service_path = mocks_dir / "fake_service.json"
    assert fake_service_path.exists()
    fake_service_data = json.loads(fake_service_path.read_text())
    return ServiceMetaDataPublished(**fake_service_data)


@pytest.fixture
def fake_service_extras() -> ServiceExtras:
    extra_example = ServiceExtras.model_config["json_schema_extra"]["examples"][2]  # type: ignore
    random_extras = ServiceExtras(**extra_example)  # type: ignore
    assert random_extras is not None
    return random_extras


@pytest.fixture
def fake_service_resources() -> ServiceResourcesDict:
    return TypeAdapter(ServiceResourcesDict).validate_python(
        ServiceResourcesDictHelpers.model_config["json_schema_extra"]["examples"][0],  # type: ignore
    )


@pytest.fixture
def fake_service_labels() -> dict[str, Any]:
    return choice(  # noqa: S311
        SimcoreServiceLabels.model_config["json_schema_extra"]["examples"]  # type: ignore
    )


@pytest.fixture
def mocked_director_service_fcts(
    minimal_app: FastAPI,
    fake_service_details: ServiceMetaDataPublished,
    fake_service_extras: ServiceExtras,
    fake_service_labels: dict[str, Any],
) -> Iterator[respx.MockRouter]:
    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=minimal_app.state.settings.DIRECTOR_V0.endpoint,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.get(
            re.compile(
                r"/services/simcore%2Fservices%2F(comp|dynamic|frontend)%2F[^/]+/\d+.\d+.\d+$"
            ),
            name="get_service",
        ).respond(
            json={"data": [fake_service_details.model_dump(mode="json", by_alias=True)]}
        )
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
        ).respond(
            json={"data": fake_service_extras.model_dump(mode="json", by_alias=True)}
        )

        yield respx_mock


@pytest.fixture
def mocked_catalog_service_fcts(
    minimal_app: FastAPI,
    fake_service_details: ServiceMetaDataPublished,
    fake_service_resources: ServiceResourcesDict,
) -> Iterator[respx.MockRouter]:
    def _mocked_service_resources(request) -> httpx.Response:
        return httpx.Response(
            httpx.codes.OK, json=jsonable_encoder(fake_service_resources, by_alias=True)
        )

    def _mocked_services_details(
        request, service_key: str, service_version: str
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=jsonable_encoder(
                fake_service_details.model_copy(
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
    fake_service_details: ServiceMetaDataPublished,
    fake_service_extras: ServiceExtras,
):
    def _mocked_services_details(
        request, service_key: str, service_version: str
    ) -> httpx.Response:
        data_published = fake_service_details.model_copy(
            update={
                "key": urllib.parse.unquote(service_key),
                "version": service_version,
                "deprecated": (
                    dt.datetime.now(tz=dt.UTC) - dt.timedelta(days=1)
                ).isoformat(),
            }
        ).model_dump(by_alias=True)

        deprecated = {
            "deprecated": (
                dt.datetime.now(tz=dt.UTC) - dt.timedelta(days=1)
            ).isoformat()
        }

        data = {**ServiceGet.model_config["json_schema_extra"]["examples"][0], **data_published, **deprecated}  # type: ignore

        payload = ServiceGet.model_validate(data)

        return httpx.Response(
            httpx.codes.OK,
            json=jsonable_encoder(
                payload,
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


@pytest.fixture(
    params=PricingPlanGet.model_config["json_schema_extra"]["examples"],
    ids=["with ec2 restriction", "without"],
)
def default_pricing_plan(request: pytest.FixtureRequest) -> PricingPlanGet:
    return PricingPlanGet(**request.param)


@pytest.fixture
def default_pricing_plan_aws_ec2_type(
    default_pricing_plan: PricingPlanGet,
) -> str | None:
    for p in default_pricing_plan.pricing_units:
        if p.default:
            if p.specific_info.aws_ec2_instances:
                return p.specific_info.aws_ec2_instances[0]
            return None
    pytest.fail("no default pricing plan defined!")
    msg = "make pylint happy by raising here"
    raise RuntimeError(msg)


@pytest.fixture
def mocked_resource_usage_tracker_service_fcts(
    minimal_app: FastAPI, default_pricing_plan: PricingPlanGet
) -> Iterator[respx.MockRouter]:
    def _mocked_service_default_pricing_plan(
        request, service_key: str, service_version: str
    ) -> httpx.Response:
        # RUT only returns values if they are in the table resource_tracker_pricing_plan_to_service
        # otherwise it returns 404s
        if "frontend" in service_key:
            # NOTE: there are typically no frontend services that have pricing plans
            return httpx.Response(status_code=status.HTTP_404_NOT_FOUND)
        return httpx.Response(
            200, json=jsonable_encoder(default_pricing_plan, by_alias=True)
        )

    def _mocked_get_pricing_unit(request, pricing_plan_id: int) -> httpx.Response:
        return httpx.Response(
            200,
            json=jsonable_encoder(
                (
                    default_pricing_plan.pricing_units[0]
                    if default_pricing_plan.pricing_units
                    else PricingUnitGet.model_config["json_schema_extra"]["examples"][0]
                ),
                by_alias=True,
            ),
        )

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=minimal_app.state.settings.DIRECTOR_V2_RESOURCE_USAGE_TRACKER.api_base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:

        respx_mock.get(
            re.compile(
                r"services/(?P<service_key>simcore/services/(comp|dynamic|frontend)/[^/]+)/(?P<service_version>[^\.]+.[^\.]+.[^/\?]+)/pricing-plan.+"
            ),
            name="get_service_default_pricing_plan",
        ).mock(side_effect=_mocked_service_default_pricing_plan)

        respx_mock.get(
            re.compile(r"pricing-plans/(?P<pricing_plan_id>\d+)/pricing-units.+"),
            name="get_pricing_unit",
        ).mock(side_effect=_mocked_get_pricing_unit)

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


@pytest.fixture
def wallet_info(faker: Faker) -> WalletInfo:
    return WalletInfo(
        wallet_id=faker.pyint(),
        wallet_name=faker.name(),
        wallet_credit_amount=Decimal(faker.pyint(min_value=12, max_value=129312)),
    )


@pytest.fixture
def fake_ec2_cpus() -> PositiveInt:
    return 4


@pytest.fixture
def fake_ec2_ram() -> ByteSize:
    return TypeAdapter(ByteSize).validate_python("4GiB")


@pytest.fixture
def mocked_clusters_keeper_service_get_instance_type_details(
    mocker: MockerFixture,
    default_pricing_plan_aws_ec2_type: str,
    fake_ec2_cpus: PositiveInt,
    fake_ec2_ram: ByteSize,
) -> mock.Mock:
    return mocker.patch(
        "simcore_service_director_v2.modules.db.repositories.comp_tasks._utils.get_instance_type_details",
        return_value=[
            EC2InstanceTypeGet(
                name=default_pricing_plan_aws_ec2_type,
                cpus=fake_ec2_cpus,
                ram=fake_ec2_ram,
            )
        ],
    )


@pytest.fixture
def mocked_clusters_keeper_service_get_instance_type_details_with_invalid_name(
    mocker: MockerFixture,
    faker: Faker,
    fake_ec2_cpus: PositiveInt,
    fake_ec2_ram: ByteSize,
) -> mock.Mock:
    return mocker.patch(
        "simcore_service_director_v2.modules.db.repositories.comp_tasks._utils.get_instance_type_details",
        return_value=[
            EC2InstanceTypeGet(
                name=faker.pystr(),
                cpus=fake_ec2_cpus,
                ram=fake_ec2_ram,
            )
        ],
    )


@pytest.fixture(
    params=ServiceResourcesDictHelpers.model_config["json_schema_extra"]["examples"]
)
def project_nodes_overrides(request: pytest.FixtureRequest) -> dict[str, Any]:
    return request.param


async def test_create_computation_with_wallet(
    minimal_configuration: None,
    mocked_director_service_fcts: respx.MockRouter,
    mocked_catalog_service_fcts: respx.MockRouter,
    mocked_resource_usage_tracker_service_fcts: respx.MockRouter,
    mocked_clusters_keeper_service_get_instance_type_details: mock.Mock,
    product_name: str,
    fake_workbench_without_outputs: dict[str, Any],
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx.AsyncClient,
    wallet_info: WalletInfo,
    project_nodes_overrides: dict[str, Any],
    default_pricing_plan_aws_ec2_type: str | None,
    aiopg_engine: aiopg.sa.Engine,
    fake_ec2_cpus: PositiveInt,
    fake_ec2_ram: ByteSize,
):
    # In billable product a wallet is passed, with a selected pricing plan
    # the pricing plan contains information about the hardware that should be used
    # this will then override the original service resources
    user = registered_user()

    proj = await project(
        user,
        project_nodes_overrides={"required_resources": project_nodes_overrides},
        workbench=fake_workbench_without_outputs,
    )
    create_computation_url = httpx.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                product_name=product_name,
                wallet_info=wallet_info,
            )
        ),
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    if default_pricing_plan_aws_ec2_type:
        mocked_clusters_keeper_service_get_instance_type_details.assert_called()
        assert (
            mocked_resource_usage_tracker_service_fcts.calls.call_count
            == len(
                [
                    v
                    for v in proj.workbench.values()
                    if to_node_class(v.key) != NodeClass.FRONTEND
                ]
            )
            * 2
        )
        # check the project nodes were really overriden now
        async with aiopg_engine.acquire() as connection:
            project_nodes_repo = ProjectNodesRepo(project_uuid=proj.uuid)
            for node in await project_nodes_repo.list(connection):
                if (
                    to_node_class(proj.workbench[NodeIDStr(f"{node.node_id}")].key)
                    != NodeClass.FRONTEND
                ):
                    assert node.required_resources
                    if DEFAULT_SINGLE_SERVICE_NAME in node.required_resources:
                        assert node.required_resources[DEFAULT_SINGLE_SERVICE_NAME][
                            "resources"
                        ] == {
                            "CPU": {
                                "limit": fake_ec2_cpus - _CPUS_SAFE_MARGIN,
                                "reservation": fake_ec2_cpus - _CPUS_SAFE_MARGIN,
                            },
                            "RAM": {
                                "limit": int(
                                    fake_ec2_ram - _RAM_SAFE_MARGIN_RATIO * fake_ec2_ram
                                ),
                                "reservation": int(
                                    fake_ec2_ram - _RAM_SAFE_MARGIN_RATIO * fake_ec2_ram
                                ),
                            },
                        }
                    elif "s4l-core" in node.required_resources:
                        # multi-container service, currently not supported
                        # hard-coded sim4life
                        assert "s4l-core" in node.required_resources
                        assert node.required_resources["s4l-core"]["resources"] == {
                            "CPU": {"limit": 4.0, "reservation": 0.1},
                            "RAM": {"limit": 17179869184, "reservation": 536870912},
                            "VRAM": {"limit": 1, "reservation": 1},
                        }
                    else:
                        # multi-container service, currently not supported
                        # hard-coded jupyterlab
                        assert "jupyter-lab" in node.required_resources
                        assert node.required_resources["jupyter-lab"]["resources"] == {
                            "CPU": {"limit": 0.1, "reservation": 0.1},
                            "RAM": {"limit": 2147483648, "reservation": 2147483648},
                        }

    else:
        mocked_clusters_keeper_service_get_instance_type_details.assert_not_called()


@pytest.mark.parametrize(
    "default_pricing_plan",
    [PricingPlanGet(**PricingPlanGet.model_config["json_schema_extra"]["examples"][0])],
)
async def test_create_computation_with_wallet_with_invalid_pricing_unit_name_raises_422(
    minimal_configuration: None,
    mocked_director_service_fcts: respx.MockRouter,
    mocked_catalog_service_fcts: respx.MockRouter,
    mocked_resource_usage_tracker_service_fcts: respx.MockRouter,
    mocked_clusters_keeper_service_get_instance_type_details_with_invalid_name: mock.Mock,
    product_name: str,
    fake_workbench_without_outputs: dict[str, Any],
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx.AsyncClient,
    wallet_info: WalletInfo,
):
    user = registered_user()
    proj = await project(
        user,
        workbench=fake_workbench_without_outputs,
    )
    create_computation_url = httpx.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                product_name=product_name,
                wallet_info=wallet_info,
            )
        ),
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    mocked_clusters_keeper_service_get_instance_type_details_with_invalid_name.assert_called_once()


@pytest.mark.parametrize(
    "default_pricing_plan",
    [
        PricingPlanGet(
            **PricingPlanGet.model_config["json_schema_extra"]["examples"][0]  # type: ignore
        )
    ],
)
async def test_create_computation_with_wallet_with_no_clusters_keeper_raises_503(
    minimal_configuration: None,
    mocked_director_service_fcts: respx.MockRouter,
    mocked_catalog_service_fcts: respx.MockRouter,
    mocked_resource_usage_tracker_service_fcts: respx.MockRouter,
    product_name: str,
    fake_workbench_without_outputs: dict[str, Any],
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx.AsyncClient,
    wallet_info: WalletInfo,
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
                product_name=product_name,
                wallet_info=wallet_info,
            )
        ),
    )
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE, response.text


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
            "required_resources": ServiceResourcesDictHelpers.model_config[
                "json_schema_extra"
            ]["examples"][0]
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
async def unusable_cluster(
    registered_user: Callable[..., dict[str, Any]],
    create_cluster: Callable[..., Awaitable[Cluster]],
) -> ClusterID:
    user = registered_user()
    created_cluster = await create_cluster(user)
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
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
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
    await create_pipeline(
        project_id=f"{proj.uuid}",
    )
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_200_OK, response.text
    returned_computation = ComputationGet.model_validate(response.json())
    assert returned_computation
    expected_computation = ComputationGet(
        id=proj.uuid,
        state=RunningState.UNKNOWN,
        pipeline_details=PipelineDetails(
            adjacency_list={}, node_states={}, progress=None
        ),
        url=TypeAdapter(AnyHttpUrl).validate_python(
            f"{async_client.base_url.join(get_computation_url)}"
        ),
        stop_url=None,
        result=None,
        iteration=None,
        cluster_id=None,
        started=None,
        stopped=None,
        submitted=None,
    )
    assert returned_computation.model_dump() == expected_computation.model_dump()


async def test_get_computation_from_not_started_computation_task(
    minimal_configuration: None,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_tasks: Callable[..., Awaitable[list[CompTaskAtDB]]],
    async_client: httpx.AsyncClient,
):
    user = registered_user()
    proj = await project(user, workbench=fake_workbench_without_outputs)
    get_computation_url = httpx.URL(
        f"/v2/computations/{proj.uuid}?user_id={user['id']}"
    )
    await create_pipeline(
        project_id=f"{proj.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    # create no task this should trigger an exception
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_409_CONFLICT, response.text

    # now create the expected tasks and the state is good again
    comp_tasks = await create_tasks(user=user, project=proj)
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_200_OK, response.text
    returned_computation = ComputationGet.model_validate(response.json())
    assert returned_computation
    expected_computation = ComputationGet(
        id=proj.uuid,
        state=RunningState.NOT_STARTED,
        pipeline_details=PipelineDetails(
            adjacency_list=TypeAdapter(dict[NodeID, list[NodeID]]).validate_python(
                fake_workbench_adjacency
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
        url=TypeAdapter(AnyHttpUrl).validate_python(
            f"{async_client.base_url.join(get_computation_url)}"
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
    assert returned_computation.model_dump(
        exclude=_CHANGED_FIELDS
    ) == expected_computation.model_dump(exclude=_CHANGED_FIELDS)
    assert returned_computation.model_dump(
        include=_CHANGED_FIELDS
    ) != expected_computation.model_dump(include=_CHANGED_FIELDS)


async def test_get_computation_from_published_computation_task(
    minimal_configuration: None,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_tasks: Callable[..., Awaitable[list[CompTaskAtDB]]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    async_client: httpx.AsyncClient,
):
    user = registered_user()
    proj = await project(user, workbench=fake_workbench_without_outputs)
    await create_pipeline(
        project_id=f"{proj.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    comp_tasks = await create_tasks(
        user=user, project=proj, state=StateType.PUBLISHED, progress=0
    )
    comp_runs = await create_comp_run(
        user=user, project=proj, result=StateType.PUBLISHED
    )
    assert comp_runs
    get_computation_url = httpx.URL(
        f"/v2/computations/{proj.uuid}?user_id={user['id']}"
    )
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_200_OK, response.text
    returned_computation = ComputationGet.model_validate(response.json())
    assert returned_computation
    expected_stop_url = async_client.base_url.join(
        f"/v2/computations/{proj.uuid}:stop?user_id={user['id']}"
    )
    expected_computation = ComputationGet(
        id=proj.uuid,
        state=RunningState.PUBLISHED,
        pipeline_details=PipelineDetails(
            adjacency_list=TypeAdapter(dict[NodeID, list[NodeID]]).validate_python(
                fake_workbench_adjacency
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
        url=TypeAdapter(AnyHttpUrl).validate_python(
            f"{async_client.base_url.join(get_computation_url)}"
        ),
        stop_url=TypeAdapter(AnyHttpUrl).validate_python(f"{expected_stop_url}"),
        result=None,
        iteration=1,
        cluster_id=DEFAULT_CLUSTER_ID,
        started=None,
        stopped=None,
        submitted=None,
    )

    _CHANGED_FIELDS = {"submitted"}
    assert returned_computation.model_dump(
        exclude=_CHANGED_FIELDS
    ) == expected_computation.model_dump(exclude=_CHANGED_FIELDS)
    assert returned_computation.model_dump(
        include=_CHANGED_FIELDS
    ) != expected_computation.model_dump(include=_CHANGED_FIELDS)
