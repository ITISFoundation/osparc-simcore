# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import Awaitable, Callable, Iterator

import pytest
import respx
from faker import Faker
from fastapi import FastAPI, status
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler import DYNAMIC_SCHEDULER_RPC_NAMESPACE
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCMethodName
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def service_status() -> DynamicServiceGet:
    return DynamicServiceGet.parse_obj(
        DynamicServiceGet.Config.schema_extra["examples"][1]
    )


@pytest.fixture
def mock_director_v2(
    node_id: NodeID, service_status: DynamicServiceGet
) -> Iterator[None]:
    with respx.mock(
        base_url="http://director-v2:8000/v2",
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as mock:
        mock.get(f"/dynamic_services/{node_id}").respond(
            status.HTTP_200_OK, text=service_status.json()
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
    mock_director_v2: None,
    app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("client")


async def test_get_state(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    service_status: DynamicServiceGet,
):
    result = await rpc_client.request(
        DYNAMIC_SCHEDULER_RPC_NAMESPACE,
        RPCMethodName("get_service_status"),
        node_id=node_id,
    )
    assert result == service_status
