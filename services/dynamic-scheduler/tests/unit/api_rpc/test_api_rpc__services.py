# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import json
from collections.abc import Awaitable, Callable, Iterator

import pytest
import respx
from faker import Faker
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    RPCDynamicServiceCreate,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler import services
from settings_library.rabbit import RabbitSettings

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def node_id_new_style(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def node_id_legacy(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def node_not_found(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def service_status_new_style() -> DynamicServiceGet:
    return DynamicServiceGet.parse_obj(
        DynamicServiceGet.Config.schema_extra["examples"][1]
    )


@pytest.fixture
def service_status_legacy() -> NodeGet:
    return NodeGet.parse_obj(NodeGet.Config.schema_extra["example"])


@pytest.fixture
def fake_director_v0_base_url() -> str:
    return "http://fake-director-v0"


@pytest.fixture
def mock_director_v0_service_state(
    fake_director_v0_base_url: str,
    node_id_legacy: NodeID,
    node_not_found: NodeID,
    service_status_legacy: NodeGet,
) -> Iterator[None]:
    with respx.mock(
        base_url=fake_director_v0_base_url,
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as mock:
        mock.get(f"/fake-status/{node_id_legacy}").respond(
            status.HTTP_200_OK,
            text=json.dumps(jsonable_encoder({"data": service_status_legacy.dict()})),
        )

        # service was not found response
        mock.get(f"fake-status/{node_not_found}").respond(status.HTTP_404_NOT_FOUND)

        yield None


@pytest.fixture
def mock_director_v2_service_state(
    node_id_new_style: NodeID,
    node_id_legacy: NodeID,
    node_not_found: NodeID,
    service_status_new_style: DynamicServiceGet,
    fake_director_v0_base_url: str,
) -> Iterator[None]:
    with respx.mock(
        base_url="http://director-v2:8000/v2",
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as mock:
        mock.get(f"/dynamic_services/{node_id_new_style}").respond(
            status.HTTP_200_OK, text=service_status_new_style.json()
        )

        # emulate redirect response to director-v0

        # this will provide a reply
        mock.get(f"/dynamic_services/{node_id_legacy}").respond(
            status.HTTP_307_TEMPORARY_REDIRECT,
            headers={
                "Location": f"{fake_director_v0_base_url}/fake-status/{node_id_legacy}"
            },
        )

        # will result in not being found
        mock.get(f"/dynamic_services/{node_not_found}").respond(
            status.HTTP_307_TEMPORARY_REDIRECT,
            headers={
                "Location": f"{fake_director_v0_base_url}/fake-status/{node_not_found}"
            },
        )

        yield None


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, rabbit_service: RabbitSettings
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
async def rpc_client(
    app_environment: EnvVarsDict,
    mock_director_v2_service_state: None,
    mock_director_v0_service_state: None,
    app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("client")


async def test_get_state(
    rpc_client: RabbitMQRPCClient,
    node_id_new_style: NodeID,
    node_id_legacy: NodeID,
    node_not_found: NodeID,
    service_status_new_style: DynamicServiceGet,
    service_status_legacy: NodeGet,
):
    # status from director-v2

    result = await services.get_service_status(rpc_client, node_id=node_id_new_style)
    assert result == service_status_new_style

    # status from director-v0
    result = await services.get_service_status(rpc_client, node_id=node_id_legacy)
    assert result == service_status_legacy

    # node not tracked any of the two directors
    result = await services.get_service_status(rpc_client, node_id=node_not_found)
    assert result == NodeGetIdle(service_state="idle", service_uuid=node_not_found)


@pytest.fixture
def rpc_dynamic_service_create() -> RPCDynamicServiceCreate:
    # one for legacy and one for new style?
    return RPCDynamicServiceCreate.parse_obj(
        RPCDynamicServiceCreate.Config.schema_extra["example"]
    )


@pytest.fixture
def mock_director_v0_service_run(
    fake_director_v0_base_url: str, service_status_legacy: NodeGet
) -> Iterator[None]:
    with respx.mock(
        base_url=fake_director_v0_base_url,
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as mock:
        mock.post("/fake-service-run").respond(
            status.HTTP_201_CREATED,
            text=json.dumps(jsonable_encoder({"data": service_status_legacy.dict()})),
        )

        yield None


@pytest.fixture
def mock_director_v2_service_run(
    is_legacy: bool,
    service_status_new_style: DynamicServiceGet,
    service_status_legacy: NodeGet,
    fake_director_v0_base_url: str,
) -> Iterator[None]:
    with respx.mock(
        base_url="http://director-v2:8000/v2",
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as mock:
        if is_legacy:
            mock.post("/dynamic_services").respond(
                status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": f"{fake_director_v0_base_url}/fake-service-run"},
            )
        else:
            mock.post("/dynamic_services").respond(
                status.HTTP_201_CREATED,
                text=service_status_new_style.json(),
            )
        yield None


@pytest.mark.parametrize("is_legacy", [True, False])
async def test_run_dynamic_service(
    mock_director_v0_service_run: None,
    mock_director_v2_service_run: None,
    rpc_client: RabbitMQRPCClient,
    rpc_dynamic_service_create: RPCDynamicServiceCreate,
    is_legacy: bool,
):
    result = await services.run_dynamic_service(
        rpc_client, rpc_dynamic_service_create=rpc_dynamic_service_create
    )

    if is_legacy:
        assert isinstance(result, NodeGet)
    else:
        assert isinstance(result, DynamicServiceGet)
