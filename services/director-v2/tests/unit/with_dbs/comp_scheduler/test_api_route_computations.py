# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-positional-arguments

import base64
import datetime as dt
import re
import urllib.parse
from collections.abc import Awaitable, Callable, Iterator
from decimal import Decimal
from typing import Any
from unittest import mock

# NOTE: respx only accepts plain httpx.Response values (it repacks them for httpx2
# clients) — see https://github.com/ITISFoundation/osparc-simcore/issues/9927
import httpx
import httpx2
import pytest
import respx
import sqlalchemy
from faker import Faker
from fastapi import FastAPI, status
from models_library.api_schemas_catalog.services import ServiceGet
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceTypeGet
from models_library.api_schemas_directorv2.computations import (
    ComputationCreate,
    ComputationDelete,
    ComputationGet,
    ComputationStop,
)
from models_library.api_schemas_directorv2.encryption import (
    JobEncryptionContextMetadata,
)
from models_library.api_schemas_directorv2.services import ServiceExtras
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    RutPricingPlanGet,
    RutPricingUnitGet,
)
from models_library.computations import CollectionRunID
from models_library.projects import ProjectAtDB
from models_library.projects_nodes import NodeState
from models_library.projects_nodes_io import NodeID
from models_library.projects_pipeline import PipelineDetails
from models_library.projects_state import RunningState
from models_library.services import ServiceMetaDataPublished
from models_library.services_resources import (
    DEFAULT_SINGLE_SERVICE_NAME,
    SERVICE_RESOURCES_DICT_EXAMPLES,
    ServiceResourcesDict,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from models_library.wallets import WalletID, WalletInfo
from pydantic import AnyHttpUrl, ByteSize, PositiveInt, TypeAdapter
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.project_nodes_pricing import (
    get_node_pricing_state,
    set_node_pricing_link,
)
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_runs import comp_runs
from simcore_postgres_database.models.comp_tasks import NodeClass, comp_tasks
from simcore_postgres_database.utils_projects_nodes import ProjectNodesRepo
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.modules.db.repositories.comp_tasks._utils import (
    _CPUS_SAFE_MARGIN,
    _RAM_SAFE_MARGIN_RATIO,
)
from simcore_service_director_v2.utils.computations import to_node_class
from simcore_service_director_v2.utils.db import RUNNING_STATE_TO_DB
from sqlalchemy.ext.asyncio import AsyncEngine

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


@pytest.fixture
def fake_service_resources() -> ServiceResourcesDict:
    return TypeAdapter[ServiceResourcesDict](ServiceResourcesDict).validate_python(
        SERVICE_RESOURCES_DICT_EXAMPLES[0],
    )


@pytest.fixture
def mocked_director_service_fcts(
    minimal_app: FastAPI,
    fake_service_details: ServiceMetaDataPublished,
) -> Iterator[respx.MockRouter]:
    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=minimal_app.state.settings.DIRECTOR_V0.endpoint,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.get(
            re.compile(r"/services/simcore%2Fservices%2F(comp|dynamic|frontend)%2F[^/]+/\d+.\d+.\d+$"),
            name="get_service",
        ).respond(json={"data": [fake_service_details.model_dump(mode="json", by_alias=True)]})

        yield respx_mock


@pytest.fixture
def mocked_catalog_service_fcts(
    minimal_app: FastAPI,
    fake_service_details: ServiceMetaDataPublished,
    fake_service_resources: ServiceResourcesDict,
    fake_service_labels: dict[str, Any],
    fake_service_extras: ServiceExtras,
) -> Iterator[respx.MockRouter]:
    def _mocked_service_resources(request) -> httpx.Response:
        return httpx.Response(httpx.codes.OK, json=jsonable_encoder(fake_service_resources, by_alias=True))

    def _mocked_services_details(request, service_key: str, service_version: str) -> httpx.Response:
        data_published = fake_service_details.model_copy(
            update={
                "key": urllib.parse.unquote(service_key),
                "version": service_version,
            }
        ).model_dump(by_alias=True)
        data = {
            **ServiceGet.model_json_schema()["examples"][0],
            **data_published,
        }
        payload = ServiceGet.model_validate(data)
        return httpx.Response(
            200,
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
                r"services/(simcore)%2F(services)%2F(comp|dynamic|frontend)%2F[^/]+/[^\.]+.[^\.]+.[^\/]+/resources"
            ),
            name="get_service_resources",
        ).mock(side_effect=_mocked_service_resources)
        respx_mock.get(
            re.compile(r"/services/simcore%2Fservices%2F(comp|dynamic|frontend)%2F[^/]+/\d+.\d+.\d+/labels"),
            name="get_service_labels",
        ).respond(json=fake_service_labels)
        respx_mock.get(
            re.compile(r"/services/simcore%2Fservices%2F(comp|dynamic|frontend)%2F[^/]+/\d+.\d+.\d+/extras"),
            name="get_service_extras",
        ).respond(json=fake_service_extras.model_dump(mode="json", by_alias=True))
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
) -> Iterator[respx.MockRouter]:
    def _mocked_services_details(request, service_key: str, service_version: str) -> httpx.Response:
        data_published = fake_service_details.model_copy(
            update={
                "key": urllib.parse.unquote(service_key),
                "version": service_version,
                "deprecated": (dt.datetime.now(tz=dt.UTC) - dt.timedelta(days=1)).isoformat(),
            }
        ).model_dump(by_alias=True)

        deprecated = {"deprecated": (dt.datetime.now(tz=dt.UTC) - dt.timedelta(days=1)).isoformat()}

        data = {
            **ServiceGet.model_json_schema()["examples"][0],
            **data_published,
            **deprecated,
        }  # type: ignore

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


assert "json_schema_extra" in RutPricingPlanGet.model_config
assert isinstance(RutPricingPlanGet.model_json_schema(), dict)
assert isinstance(RutPricingPlanGet.model_json_schema()["examples"], list)


@pytest.fixture(
    params=[
        RutPricingPlanGet.model_json_schema()["examples"][0],
        RutPricingPlanGet.model_json_schema()["examples"][1],
    ],
    ids=["with ec2 restriction", "without"],
)
def default_pricing_plan(request: pytest.FixtureRequest) -> RutPricingPlanGet:
    return RutPricingPlanGet(**request.param)


@pytest.fixture
def default_pricing_plan_aws_ec2_type(
    default_pricing_plan: RutPricingPlanGet,
) -> str | None:
    assert default_pricing_plan.pricing_units
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
    minimal_app: FastAPI, default_pricing_plan: RutPricingPlanGet
) -> Iterator[respx.MockRouter]:
    def _mocked_service_default_pricing_plan(request, service_key: str, service_version: str) -> httpx.Response:
        # RUT only returns values if they are in the table resource_tracker_pricing_plan_to_service
        # otherwise it returns 404s
        if "frontend" in service_key:
            # NOTE: there are typically no frontend services that have pricing plans
            return httpx.Response(status_code=status.HTTP_404_NOT_FOUND)
        return httpx.Response(200, json=jsonable_encoder(default_pricing_plan, by_alias=True))

    def _mocked_get_pricing_unit(request, pricing_plan_id: int) -> httpx.Response:
        assert "json_schema_extra" in RutPricingUnitGet.model_config
        assert isinstance(RutPricingUnitGet.model_json_schema(), dict)
        assert isinstance(RutPricingUnitGet.model_json_schema()["examples"], list)
        return httpx.Response(
            200,
            json=jsonable_encoder(
                (
                    default_pricing_plan.pricing_units[0]
                    if default_pricing_plan.pricing_units
                    else RutPricingUnitGet.model_json_schema()["examples"][0]
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
def product_api_base_url(faker: Faker) -> AnyHttpUrl:
    return TypeAdapter(AnyHttpUrl).validate_python(faker.url())


async def test_computation_create_validators(
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    fake_workbench_without_outputs: dict[str, Any],
    product_name: str,
    product_api_base_url: AnyHttpUrl,
    with_product: dict[str, Any],
    fake_collection_run_id: CollectionRunID,
):
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    ComputationCreate(
        user_id=user["id"],
        project_id=proj.uuid,
        product_name=product_name,
        product_api_base_url=product_api_base_url,
        use_on_demand_clusters=True,
    )
    ComputationCreate(
        user_id=user["id"],
        project_id=proj.uuid,
        product_name=product_name,
        product_api_base_url=product_api_base_url,
        use_on_demand_clusters=False,
    )


async def test_create_computation(
    minimal_configuration: None,
    mocked_director_service_fcts: respx.MockRouter,
    mocked_catalog_service_fcts: respx.MockRouter,
    product_name: str,
    product_api_base_url: AnyHttpUrl,
    fake_workbench_without_outputs: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx2.AsyncClient,
    fake_collection_run_id: CollectionRunID,
    sqlalchemy_async_engine: AsyncEngine,
):
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    create_computation_url = httpx2.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                product_name=product_name,
                product_api_base_url=product_api_base_url,
            )
        ),
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text

    # CHARACTERIZATION (D6): without a wallet the computation is NOT billed, so
    # director-v2 must leave the projects pricing state completely untouched:
    # no pricing links are created for any node.
    pricing_state = await get_node_pricing_state(sqlalchemy_async_engine, proj.uuid)
    assert pricing_state
    for node_state in pricing_state.values():
        assert node_state.pricing_plan_id is None
        assert node_state.pricing_unit_id is None


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


@pytest.fixture(params=SERVICE_RESOURCES_DICT_EXAMPLES)
def project_nodes_overrides(request: pytest.FixtureRequest) -> dict[str, Any]:
    return request.param


@pytest.mark.epic("sanderegg/9851", flips_in="PR3")
async def test_create_computation_with_wallet(
    minimal_configuration: None,
    mocked_director_service_fcts: respx.MockRouter,
    mocked_catalog_service_fcts: respx.MockRouter,
    mocked_resource_usage_tracker_service_fcts: respx.MockRouter,
    mocked_clusters_keeper_service_get_instance_type_details: mock.Mock,
    product_name: str,
    product_api_base_url: AnyHttpUrl,
    fake_workbench_without_outputs: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx2.AsyncClient,
    wallet_info: WalletInfo,
    project_nodes_overrides: dict[str, Any],
    default_pricing_plan_aws_ec2_type: str | None,
    sqlalchemy_async_engine: AsyncEngine,
    fake_ec2_cpus: PositiveInt,
    fake_ec2_ram: ByteSize,
    fake_collection_run_id: CollectionRunID,
):
    # In billable product a wallet is passed, with a selected pricing plan
    # the pricing plan contains information about the hardware that should be used
    # this will then override the original service resources
    user = create_registered_user()

    proj = await create_project(
        user,
        project_nodes_overrides={"required_resources": project_nodes_overrides},
        workbench=fake_workbench_without_outputs,
    )
    create_computation_url = httpx2.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                product_name=product_name,
                product_api_base_url=product_api_base_url,
                wallet_info=wallet_info,
            )
        ),
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    if default_pricing_plan_aws_ec2_type:
        # clusters-keeper is asked once for all the nodes together
        mocked_clusters_keeper_service_get_instance_type_details.assert_called_once()
        # RUT is asked once per distinct non-frontend service (its default pricing) and once for
        # the pricing unit those services all share
        non_frontend_service_key_versions = {
            (v.key, v.version) for v in proj.workbench.values() if to_node_class(v.key) != NodeClass.FRONTEND
        }
        assert mocked_resource_usage_tracker_service_fcts.calls.call_count == len(non_frontend_service_key_versions) + 1
        # check the project nodes were really overridden now
        async with sqlalchemy_async_engine.connect() as connection:
            project_nodes_repo = ProjectNodesRepo(project_uuid=proj.uuid)
            for node in await project_nodes_repo.list(connection):
                if to_node_class(proj.workbench[f"{node.node_id}"].key) != NodeClass.FRONTEND:
                    assert node.required_resources
                    if DEFAULT_SINGLE_SERVICE_NAME in node.required_resources:
                        assert node.required_resources[DEFAULT_SINGLE_SERVICE_NAME]["resources"] == {
                            "CPU": {
                                "limit": fake_ec2_cpus - _CPUS_SAFE_MARGIN,
                                "reservation": fake_ec2_cpus - _CPUS_SAFE_MARGIN,
                            },
                            "RAM": {
                                "limit": int(fake_ec2_ram - _RAM_SAFE_MARGIN_RATIO * fake_ec2_ram),
                                "reservation": int(fake_ec2_ram - _RAM_SAFE_MARGIN_RATIO * fake_ec2_ram),
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

    # CHARACTERIZATION (D1/D3/D4/D5): the upsert *lazily linked* the default
    # pricing unit onto EVERY non-frontend node (comp AND dynamic, including the
    # multi-container ones) and stamped its pricing info onto comp_tasks.
    # Frontend (file-picker) nodes are never priced.
    # ⚠️ PR 3 of the pricing/resources ownership rework makes director-v2 stop
    #    creating these links (the web server owns them); dynamic nodes are then
    #    neither linked nor sized here — update these expectations then.
    # ⚠️ D3: note the dynamic node above was sized with the dask-worker-style
    #    margins (same as computational), not the dynamic sidecar ones.
    pricing_state = await get_node_pricing_state(sqlalchemy_async_engine, proj.uuid)
    assert pricing_state
    for node_id, node_state in pricing_state.items():
        if to_node_class(proj.workbench[f"{node_id}"].key) == NodeClass.FRONTEND:
            assert node_state.pricing_plan_id is None
            assert node_state.pricing_unit_id is None
        else:
            assert node_state.pricing_plan_id == 1  # from the mocked default plan
            assert node_state.pricing_unit_id == 1  # from the mocked default unit

    async with sqlalchemy_async_engine.connect() as connection:
        task_rows = (
            await connection.execute(
                sqlalchemy.select(comp_tasks.c.node_id, comp_tasks.c.pricing_info).where(
                    comp_tasks.c.project_id == f"{proj.uuid}"
                )
            )
        ).all()
    assert task_rows
    for node_id, pricing_info in task_rows:
        if to_node_class(proj.workbench[f"{node_id}"].key) == NodeClass.FRONTEND:
            assert pricing_info is None
        else:
            assert pricing_info is not None
            assert pricing_info["pricing_plan_id"] == 1
            assert pricing_info["pricing_unit_id"] == 1
            assert pricing_info["pricing_unit_cost_id"] == 1


@pytest.mark.parametrize(
    "default_pricing_plan",
    [RutPricingPlanGet.model_validate(RutPricingPlanGet.model_json_schema()["examples"][0])],
)
async def test_create_computation_with_wallet_with_invalid_pricing_unit_name_raises_404(
    minimal_configuration: None,
    mocked_director_service_fcts: respx.MockRouter,
    mocked_catalog_service_fcts: respx.MockRouter,
    mocked_resource_usage_tracker_service_fcts: respx.MockRouter,
    mocked_clusters_keeper_service_get_instance_type_details_with_invalid_name: mock.Mock,
    product_name: str,
    product_api_base_url: AnyHttpUrl,
    fake_workbench_without_outputs: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx2.AsyncClient,
    wallet_info: WalletInfo,
    fake_collection_run_id: CollectionRunID,
):
    user = create_registered_user()
    proj = await create_project(
        user,
        workbench=fake_workbench_without_outputs,
    )
    create_computation_url = httpx2.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                product_name=product_name,
                product_api_base_url=product_api_base_url,
                wallet_info=wallet_info,
            )
        ),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    mocked_clusters_keeper_service_get_instance_type_details_with_invalid_name.assert_called_once()


@pytest.mark.parametrize(
    "default_pricing_plan",
    [RutPricingPlanGet.model_validate(RutPricingPlanGet.model_json_schema()["examples"][0])],
)
async def test_create_computation_with_wallet_keeps_pre_linked_pricing_unit_and_sizes_from_it(
    minimal_configuration: None,
    mocked_director_service_fcts: respx.MockRouter,
    mocked_catalog_service_fcts: respx.MockRouter,
    mocked_resource_usage_tracker_service_fcts: respx.MockRouter,
    mocked_clusters_keeper_service_get_instance_type_details: mock.Mock,
    product_name: str,
    product_api_base_url: AnyHttpUrl,
    fake_workbench_without_outputs: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx2.AsyncClient,
    wallet_info: WalletInfo,
    sqlalchemy_async_engine: AsyncEngine,
    fake_ec2_cpus: PositiveInt,
    fake_ec2_ram: ByteSize,
    fake_collection_run_id: CollectionRunID,
):
    # CHARACTERIZATION (D2): a node that ALREADY has a pricing-unit link keeps it:
    # director-v2 does not re-link it to the product default (RUT is never asked
    # for a service default) and still sizes the node from the LINKED unit's
    # hardware. This is exactly what the pricing/resources ownership rework
    # (PR 3) relies on: the web server pre-creates the links and director-v2
    # only reads them.
    user = create_registered_user()
    proj = await create_project(
        user,
        project_nodes_overrides={"required_resources": SERVICE_RESOURCES_DICT_EXAMPLES[0]},
        workbench=fake_workbench_without_outputs,
    )

    # link every non-frontend node to a unit that is NOT the mocked default
    # (the ids have no FKs, so arbitrary values are fine here)
    pre_linked_plan_id, pre_linked_unit_id = 1, 99
    non_frontend_node_ids = [
        NodeID(node_id) for node_id, node in proj.workbench.items() if to_node_class(node.key) != NodeClass.FRONTEND
    ]
    assert non_frontend_node_ids
    for node_id in non_frontend_node_ids:
        await set_node_pricing_link(
            sqlalchemy_async_engine,
            proj.uuid,
            node_id,
            pricing_plan_id=pre_linked_plan_id,
            pricing_unit_id=pre_linked_unit_id,
        )

    create_computation_url = httpx2.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                product_name=product_name,
                product_api_base_url=product_api_base_url,
                wallet_info=wallet_info,
            )
        ),
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text

    # no node needed a default: they all had a link already
    assert mocked_resource_usage_tracker_service_fcts["get_service_default_pricing_plan"].calls.call_count == 0

    pricing_state = await get_node_pricing_state(sqlalchemy_async_engine, proj.uuid)
    for node_id, node_state in pricing_state.items():
        if to_node_class(proj.workbench[f"{node_id}"].key) == NodeClass.FRONTEND:
            assert node_state.pricing_unit_id is None
            continue
        assert node_state.pricing_plan_id == pre_linked_plan_id
        assert node_state.pricing_unit_id == pre_linked_unit_id
        # the linked unit's hardware (the mocked default unit's EC2 type) sized the node
        assert node_state.required_resources is not None
        assert node_state.required_resources[DEFAULT_SINGLE_SERVICE_NAME]["resources"] == {
            "CPU": {
                "limit": fake_ec2_cpus - _CPUS_SAFE_MARGIN,
                "reservation": fake_ec2_cpus - _CPUS_SAFE_MARGIN,
            },
            "RAM": {
                "limit": int(fake_ec2_ram - _RAM_SAFE_MARGIN_RATIO * fake_ec2_ram),
                "reservation": int(fake_ec2_ram - _RAM_SAFE_MARGIN_RATIO * fake_ec2_ram),
            },
        }

    async with sqlalchemy_async_engine.connect() as connection:
        task_rows = (
            await connection.execute(
                sqlalchemy.select(comp_tasks.c.node_id, comp_tasks.c.pricing_info).where(
                    comp_tasks.c.project_id == f"{proj.uuid}"
                )
            )
        ).all()
    for node_id, pricing_info in task_rows:
        if f"{node_id}" not in {f"{n}" for n in non_frontend_node_ids}:
            assert pricing_info is None
        else:
            assert pricing_info is not None
            assert pricing_info["pricing_plan_id"] == pre_linked_plan_id
            assert pricing_info["pricing_unit_id"] == pre_linked_unit_id
            # cost id comes from the (mocked) RUT unit response
            assert pricing_info["pricing_unit_cost_id"] == 1


@pytest.mark.parametrize(
    "default_pricing_plan",
    [
        RutPricingPlanGet(
            **RutPricingPlanGet.model_json_schema()["examples"][0]  # type: ignore
        )
    ],
)
async def test_create_computation_with_wallet_with_no_clusters_keeper_raises_503(
    minimal_configuration: None,
    mocked_director_service_fcts: respx.MockRouter,
    mocked_catalog_service_fcts: respx.MockRouter,
    mocked_resource_usage_tracker_service_fcts: respx.MockRouter,
    product_name: str,
    product_api_base_url: AnyHttpUrl,
    fake_workbench_without_outputs: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx2.AsyncClient,
    wallet_info: WalletInfo,
    fake_collection_run_id: CollectionRunID,
):
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    create_computation_url = httpx2.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                product_name=product_name,
                product_api_base_url=product_api_base_url,
                wallet_info=wallet_info,
            )
        ),
    )
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE, response.text


async def test_start_computation_without_product_fails(
    minimal_configuration: None,
    mocked_director_service_fcts: respx.MockRouter,
    mocked_catalog_service_fcts: respx.MockRouter,
    product_name: str,
    fake_workbench_without_outputs: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx2.AsyncClient,
    fake_collection_run_id: CollectionRunID,
):
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    create_computation_url = httpx2.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json={
            "user_id": f"{user['id']}",
            "project_id": f"{proj.uuid}",
            "start_pipeline": f"{True}",
            "collection_run_id": f"{fake_collection_run_id}",
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, response.text


async def test_start_computation_without_collection_run_id_fails(
    minimal_configuration: None,
    mocked_director_service_fcts: respx.MockRouter,
    mocked_catalog_service_fcts: respx.MockRouter,
    product_name: str,
    fake_workbench_without_outputs: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx2.AsyncClient,
):
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    create_computation_url = httpx2.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json={
            "product_name": product_name,
            "user_id": f"{user['id']}",
            "project_id": f"{proj.uuid}",
            "start_pipeline": f"{True}",
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, response.text


async def test_start_computation(
    minimal_configuration: None,
    mocked_director_service_fcts: respx.MockRouter,
    mocked_catalog_service_fcts: respx.MockRouter,
    product_name: str,
    product_api_base_url: AnyHttpUrl,
    fake_workbench_without_outputs: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx2.AsyncClient,
    fake_collection_run_id: CollectionRunID,
):
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    create_computation_url = httpx2.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                start_pipeline=True,
                product_name=product_name,
                product_api_base_url=product_api_base_url,
                collection_run_id=fake_collection_run_id,
            )
        ),
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    mocked_get_service_resources = mocked_catalog_service_fcts["get_service_resources"]
    # no resources are defined by default, so the catalog is asked — once per distinct service,
    # not once per node
    assert mocked_get_service_resources.call_count == len(
        {(node["key"], node["version"]) for node in fake_workbench_without_outputs.values()}
    )


async def test_start_computation_with_encryption_propagates_context_to_pipeline(
    minimal_configuration: None,
    mocked_director_service_fcts: respx.MockRouter,
    mocked_catalog_service_fcts: respx.MockRouter,
    product_name: str,
    product_api_base_url: AnyHttpUrl,
    fake_workbench_without_outputs: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx2.AsyncClient,
    fake_collection_run_id: CollectionRunID,
    mocker: MockerFixture,
):
    mocked_run_new_pipeline = mocker.patch(
        "simcore_service_director_v2.api.routes.computations.run_new_pipeline",
        autospec=True,
    )
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)

    root_key_b64 = base64.b64encode(b"0" * 32).decode("ascii")
    # encryption is defined per computational node of the pipeline
    encrypted_node_id = next(iter(proj.workbench))
    node_input_port_to_file_id = {"input_1": "input_1"}

    create_computation_url = httpx2.URL("/v2/computations")
    body = jsonable_encoder(
        ComputationCreate(
            user_id=user["id"],
            project_id=proj.uuid,
            start_pipeline=True,
            product_name=product_name,
            product_api_base_url=product_api_base_url,
            collection_run_id=fake_collection_run_id,
        )
    )
    # NOTE: the SecretStr root_key would be masked by jsonable_encoder, so we inject the
    # encryption payload as a raw JSON dict carrying the base64-encoded (fake) ciphertext
    body["encryption"] = {
        "encrypted_root_key": root_key_b64,
        "input_port_to_file_id": {encrypted_node_id: node_input_port_to_file_id},
    }
    response = await async_client.post(create_computation_url, json=body)
    assert response.status_code == status.HTTP_201_CREATED, response.text

    mocked_run_new_pipeline.assert_called_once()
    run_metadata = mocked_run_new_pipeline.call_args.kwargs["run_metadata"]
    stored_encryption = run_metadata["encryption"]
    assert stored_encryption["encrypted_root_key"] == root_key_b64
    reparsed = JobEncryptionContextMetadata.model_validate(stored_encryption)
    assert reparsed.input_port_to_file_id == {NodeID(encrypted_node_id): node_input_port_to_file_id}


async def test_start_computation_with_project_node_resources_defined(
    minimal_configuration: None,
    mocked_director_service_fcts: respx.MockRouter,
    mocked_catalog_service_fcts: respx.MockRouter,
    product_name: str,
    product_api_base_url: AnyHttpUrl,
    fake_workbench_without_outputs: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx2.AsyncClient,
    fake_collection_run_id: CollectionRunID,
):
    user = create_registered_user()
    proj = await create_project(
        user,
        project_nodes_overrides={"required_resources": SERVICE_RESOURCES_DICT_EXAMPLES[0]},
        workbench=fake_workbench_without_outputs,
    )
    create_computation_url = httpx2.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                start_pipeline=True,
                product_name=product_name,
                product_api_base_url=product_api_base_url,
                collection_run_id=fake_collection_run_id,
            )
        ),
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    mocked_get_service_resources = mocked_catalog_service_fcts["get_service_resources"]
    # there should be no calls to the catalog as there are resources defined, so no need to call the catalog
    assert mocked_get_service_resources.call_count == 0


async def test_start_computation_with_deprecated_services_raises_409(
    minimal_configuration: None,
    mocked_director_service_fcts: respx.MockRouter,
    mocked_catalog_service_fcts_deprecated: respx.MockRouter,
    product_name: str,
    product_api_base_url: AnyHttpUrl,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx2.AsyncClient,
    fake_collection_run_id: CollectionRunID,
):
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    create_computation_url = httpx2.URL("/v2/computations")
    response = await async_client.post(
        create_computation_url,
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                start_pipeline=True,
                product_name=product_name,
                product_api_base_url=product_api_base_url,
                collection_run_id=fake_collection_run_id,
            )
        ),
    )
    assert response.status_code == status.HTTP_409_CONFLICT, response.text


async def test_get_computation_from_empty_project(
    minimal_configuration: None,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    faker: Faker,
    async_client: httpx2.AsyncClient,
):
    user = create_registered_user()
    get_computation_url = httpx2.URL(f"/v2/computations/{faker.uuid4()}?user_id={user['id']}")
    # the project exists but there is no pipeline yet
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    # create the project
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    get_computation_url = httpx2.URL(f"/v2/computations/{proj.uuid}?user_id={user['id']}")
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
        state=RunningState.NOT_STARTED,
        pipeline_details=PipelineDetails(adjacency_list={}, node_states={}, progress=None),
        url=TypeAdapter(AnyHttpUrl).validate_python(f"{async_client.base_url.join(get_computation_url)}"),
        stop_url=None,
        result=None,
        iteration=None,
        started=None,
        stopped=None,
        submitted=None,
    )
    assert returned_computation.model_dump() == expected_computation.model_dump()


async def test_get_computation_from_not_started_computation_task(
    minimal_configuration: None,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_tasks_from_project: Callable[..., Awaitable[list[CompTaskAtDB]]],
    async_client: httpx2.AsyncClient,
):
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    get_computation_url = httpx2.URL(f"/v2/computations/{proj.uuid}?user_id={user['id']}")
    await create_pipeline(
        project_id=f"{proj.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    # create no task this should trigger an exception
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_409_CONFLICT, response.text

    # now create the expected tasks and the state is good again
    comp_tasks = await create_tasks_from_project(user=user, project=proj)
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_200_OK, response.text
    returned_computation = ComputationGet.model_validate(response.json())
    assert returned_computation
    expected_computation = ComputationGet(
        id=proj.uuid,
        state=RunningState.NOT_STARTED,
        pipeline_details=PipelineDetails(
            adjacency_list=TypeAdapter(dict[NodeID, list[NodeID]]).validate_python(fake_workbench_adjacency),
            progress=0,
            node_states={
                t.node_id: NodeState(
                    modified=True,
                    current_status=RunningState.NOT_STARTED,
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
        url=TypeAdapter(AnyHttpUrl).validate_python(f"{async_client.base_url.join(get_computation_url)}"),
        stop_url=None,
        result=None,
        iteration=None,
        started=None,
        stopped=None,
        submitted=None,
    )
    assert returned_computation == expected_computation


async def test_get_computation_from_published_computation_task(
    minimal_configuration: None,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_tasks_from_project: Callable[..., Awaitable[list[CompTaskAtDB]]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    async_client: httpx2.AsyncClient,
):
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    await create_pipeline(
        project_id=f"{proj.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    comp_tasks = await create_tasks_from_project(user=user, project=proj, state=StateType.PUBLISHED, progress=0)
    comp_runs = await create_comp_run(
        user=user,
        project=proj,
        result=StateType.PUBLISHED,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    assert comp_runs
    get_computation_url = httpx2.URL(f"/v2/computations/{proj.uuid}?user_id={user['id']}")
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_200_OK, response.text
    returned_computation = ComputationGet.model_validate(response.json())
    assert returned_computation
    expected_stop_url = async_client.base_url.join(f"/v2/computations/{proj.uuid}:stop?user_id={user['id']}")
    expected_computation = ComputationGet(
        id=proj.uuid,
        state=RunningState.PUBLISHED,
        pipeline_details=PipelineDetails(
            adjacency_list=TypeAdapter(dict[NodeID, list[NodeID]]).validate_python(fake_workbench_adjacency),
            node_states={
                t.node_id: NodeState(
                    modified=True,
                    current_status=RunningState.PUBLISHED,
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
        url=TypeAdapter(AnyHttpUrl).validate_python(f"{async_client.base_url.join(get_computation_url)}"),
        stop_url=TypeAdapter(AnyHttpUrl).validate_python(f"{expected_stop_url}"),
        result=None,
        iteration=1,
        started=None,
        stopped=None,
        submitted=None,
    )

    _CHANGED_FIELDS = {"submitted"}
    assert returned_computation.model_dump(exclude=_CHANGED_FIELDS) == expected_computation.model_dump(
        exclude=_CHANGED_FIELDS
    )
    assert returned_computation.model_dump(include=_CHANGED_FIELDS) != expected_computation.model_dump(
        include=_CHANGED_FIELDS
    )


async def test_delete_computation_success(
    minimal_configuration: None,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    async_client: httpx2.AsyncClient,
):
    """Test successful pipeline deletion when pipeline is not running."""
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    await create_pipeline(project_id=f"{proj.uuid}", dag_adjacency_list=fake_workbench_adjacency)
    await create_comp_run(
        user=user,
        project=proj,
        result=StateType.SUCCESS,
        dag_adjacency_list=fake_workbench_adjacency,
    )

    delete_computation_url = httpx2.URL(f"/v2/computations/{proj.uuid}?user_id={user['id']}")
    response = await async_client.request(
        "DELETE",
        delete_computation_url,
        json=ComputationDelete(user_id=user["id"], force=False).model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text

    # calling a second time returns 204 as well, since the pipeline is already deleted (idempotent)
    response = await async_client.request(
        "DELETE",
        delete_computation_url,
        json=ComputationDelete(user_id=user["id"], force=False).model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text


async def test_delete_computation_fails_when_pipeline_does_not_stop_in_time(
    minimal_configuration: None,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    async_client: httpx2.AsyncClient,
    mocker: MockerFixture,
):
    """Test that deletion raises 409 when pipeline doesn't stop within timeout."""
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    await create_pipeline(project_id=f"{proj.uuid}", dag_adjacency_list=fake_workbench_adjacency)

    # Create a comp_run that is always in PUBLISHED (running) state
    await create_comp_run(
        user=user,
        project=proj,
        result=StateType.PUBLISHED,
        dag_adjacency_list=fake_workbench_adjacency,
    )

    # Mock stop_pipeline to succeed silently
    mocker.patch(
        "simcore_service_director_v2.api.routes.computations.stop_pipeline",
        autospec=True,
    )

    # NOTE: check_pipeline_stopped is a nested function and cannot be mocked directly.
    # Instead, use a short wait_for so the real retry loop times out quickly: since the
    # comp_run stays PUBLISHED (no scheduler advances it in this test), the pipeline
    # never reports as stopped.
    delete_computation_url = httpx2.URL(f"/v2/computations/{proj.uuid}?user_id={user['id']}")
    response = await async_client.request(
        "DELETE",
        delete_computation_url,
        json=ComputationDelete(user_id=user["id"], force=True, wait_for=dt.timedelta(seconds=0.2)).model_dump(
            mode="json"
        ),
    )
    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    assert "could not be stopped properly after" in response.text.lower()


async def test_stop_computation_can_be_called_again_once_pipeline_stopped(
    minimal_configuration: None,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    async_client: httpx2.AsyncClient,
    sqlalchemy_async_engine: AsyncEngine,
):
    """Stopping a computation must be safe to call again once the pipeline has
    actually stopped, without raising any error (e.g. it must not rely on the
    now-removed ComputationalSchedulerError handling)."""
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    await create_pipeline(project_id=f"{proj.uuid}", dag_adjacency_list=fake_workbench_adjacency)
    await create_comp_run(
        user=user,
        project=proj,
        result=StateType.PUBLISHED,
        dag_adjacency_list=fake_workbench_adjacency,
    )

    stop_computation_url = httpx2.URL(f"/v2/computations/{proj.uuid}:stop")

    # first call: the pipeline is running, so it gets marked for cancellation
    response = await async_client.post(
        stop_computation_url,
        json=ComputationStop(user_id=user["id"]).model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_202_ACCEPTED, response.text

    # wait for the pipeline to stop (simulates the scheduler eventually reporting it as stopped)
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_runs.update()
            .where((comp_runs.c.user_id == user["id"]) & (comp_runs.c.project_uuid == f"{proj.uuid}"))
            .values(result=RUNNING_STATE_TO_DB[RunningState.ABORTED])
        )

    # second call: the pipeline is already stopped, this must not raise
    response = await async_client.post(
        stop_computation_url,
        json=ComputationStop(user_id=user["id"]).model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_202_ACCEPTED, response.text


async def test_stop_computation_that_was_never_run_does_not_fail(
    minimal_configuration: None,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    async_client: httpx2.AsyncClient,
):
    """Stopping a computation that has a pipeline but was never run (i.e. no
    comp_run entry exists yet) must not fail (e.g. it must not raise/propagate
    ComputationalRunNotFoundError)."""
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    await create_pipeline(project_id=f"{proj.uuid}", dag_adjacency_list=fake_workbench_adjacency)

    # NOTE: no comp_run is created here, simulating a pipeline that was never started

    stop_computation_url = httpx2.URL(f"/v2/computations/{proj.uuid}:stop")
    response = await async_client.post(
        stop_computation_url,
        json=ComputationStop(user_id=user["id"]).model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_202_ACCEPTED, response.text
    returned_computation = ComputationGet.model_validate(response.json())
    assert returned_computation.state == RunningState.NOT_STARTED
    assert returned_computation.iteration is None
    assert returned_computation.started is None
    assert returned_computation.stopped is None
    assert returned_computation.submitted is None


#
# CHARACTERIZATION TESTS (pin the state of the DB, not the code that produces it)
#


@pytest.mark.parametrize(
    "default_pricing_plan",
    [RutPricingPlanGet.model_validate(RutPricingPlanGet.model_json_schema()["examples"][0])],
)
async def test_start_computation_with_zero_credit_wallet_aborts_published_tasks(
    minimal_configuration: None,
    mocked_director_service_fcts: respx.MockRouter,
    mocked_catalog_service_fcts: respx.MockRouter,
    mocked_resource_usage_tracker_service_fcts: respx.MockRouter,
    mocked_clusters_keeper_service_get_instance_type_details: mock.Mock,
    product_name: str,
    product_api_base_url: AnyHttpUrl,
    fake_workbench_without_outputs: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    async_client: httpx2.AsyncClient,
    faker: Faker,
    fake_collection_run_id: CollectionRunID,
    sqlalchemy_async_engine: AsyncEngine,
):
    # CHARACTERIZATION (D7): starting a pipeline in a billed product with a wallet that has
    # zero credits and a non-zero-cost pricing unit must (a) return 402, (b) persist every
    # task that would have been published as ABORTED and (c) never create a run.
    # The pricing/resources ownership rework (PRs 1-3) must keep this behavior.
    zero_credit_wallet = WalletInfo(
        wallet_id=WalletID(faker.pyint()),
        wallet_name=faker.name(),
        wallet_credit_amount=Decimal(0),
    )
    assert mocked_resource_usage_tracker_service_fcts  # the default unit has cost > 0

    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)

    response = await async_client.post(
        httpx2.URL("/v2/computations"),
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                start_pipeline=True,
                product_name=product_name,
                product_api_base_url=product_api_base_url,
                collection_run_id=fake_collection_run_id,
                wallet_info=zero_credit_wallet,
            )
        ),
    )
    assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED, response.text

    async with sqlalchemy_async_engine.connect() as connection:
        task_rows = (
            await connection.execute(
                sqlalchemy.select(comp_tasks.c.node_id, comp_tasks.c.state).where(
                    comp_tasks.c.project_id == f"{proj.uuid}"
                )
            )
        ).all()
        assert task_rows
        for node_id, state in task_rows:
            node_key = proj.workbench[f"{node_id}"].key
            if to_node_class(node_key) == NodeClass.COMPUTATIONAL:
                # it was selected for the run (PUBLISHED) and aborted for insufficient credits
                assert state == StateType.ABORTED, f"node {node_id} (comp) must be ABORTED, got {state}"
            else:
                # never published -> never aborted
                assert state != StateType.PUBLISHED, f"node {node_id} must not be PUBLISHED"

        runs = (
            await connection.execute(
                sqlalchemy.select(comp_runs.c.run_id).where(comp_runs.c.project_uuid == f"{proj.uuid}")
            )
        ).all()
    assert not runs, "no run may be created when the start is rejected for insufficient credits"


@pytest.mark.parametrize(
    "default_pricing_plan",
    [RutPricingPlanGet.model_validate(RutPricingPlanGet.model_json_schema()["examples"][0])],
)
async def test_run_metadata_keeps_the_wallet_of_the_start(
    minimal_configuration: None,
    mocked_director_service_fcts: respx.MockRouter,
    mocked_catalog_service_fcts: respx.MockRouter,
    mocked_resource_usage_tracker_service_fcts: respx.MockRouter,
    mocked_clusters_keeper_service_get_instance_type_details: mock.Mock,
    product_name: str,
    product_api_base_url: AnyHttpUrl,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    async_client: httpx2.AsyncClient,
    wallet_info: WalletInfo,
    faker: Faker,
    fake_collection_run_id: CollectionRunID,
    sqlalchemy_async_engine: AsyncEngine,
):
    # CHARACTERIZATION (D8): the wallet a run is billed to is a SNAPSHOT taken at start time and
    # persisted in `comp_runs.metadata`. A later computation that carries a DIFFERENT wallet must
    # not be able to change it: while the pipeline is running, it is rejected (409) and the
    # metadata of the started run stays the same. The pricing/resources ownership rework
    # (PRs 1-3) must keep this behavior.
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    await create_pipeline(project_id=f"{proj.uuid}", dag_adjacency_list=fake_workbench_adjacency)

    response = await async_client.post(
        httpx2.URL("/v2/computations"),
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                start_pipeline=True,
                product_name=product_name,
                product_api_base_url=product_api_base_url,
                collection_run_id=fake_collection_run_id,
                wallet_info=wallet_info,
            )
        ),
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text

    async def _get_run_metadata() -> dict[str, Any]:
        async with sqlalchemy_async_engine.connect() as connection:
            metadata = (
                await connection.execute(
                    sqlalchemy.select(comp_runs.c.metadata)
                    .where(comp_runs.c.project_uuid == f"{proj.uuid}")
                    .order_by(comp_runs.c.iteration.desc())
                    .limit(1)
                )
            ).scalar_one()
        assert metadata
        return metadata

    run_metadata = await _get_run_metadata()
    assert run_metadata["wallet_id"] == wallet_info.wallet_id
    assert run_metadata["wallet_name"] == wallet_info.wallet_name

    # another computation, now pointing to a DIFFERENT wallet, while the run is still publishing
    other_wallet = WalletInfo(
        wallet_id=WalletID(faker.pyint(min_value=10)),
        wallet_name=faker.name(),
        wallet_credit_amount=Decimal(100),
    )
    response = await async_client.post(
        httpx2.URL("/v2/computations"),
        json=jsonable_encoder(
            ComputationCreate(
                user_id=user["id"],
                project_id=proj.uuid,
                product_name=product_name,
                product_api_base_url=product_api_base_url,
                wallet_info=other_wallet,
            )
        ),
    )
    assert response.status_code == status.HTTP_409_CONFLICT, response.text

    # the started run still bills to the wallet of its start
    run_metadata = await _get_run_metadata()
    assert run_metadata["wallet_id"] == wallet_info.wallet_id
    assert run_metadata["wallet_name"] == wallet_info.wallet_name
