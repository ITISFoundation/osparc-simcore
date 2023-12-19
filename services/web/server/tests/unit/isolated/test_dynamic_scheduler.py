# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from unittest.mock import AsyncMock

import pytest
from faker import Faker
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    RPCDynamicServiceCreate,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from pytest_mock import MockerFixture
from simcore_service_webserver.dynamic_scheduler.api import (
    get_dynamic_service,
    run_dynamic_service,
)


@pytest.fixture
def mocked_app() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def mock_rpc_client(
    mocker: MockerFixture, expected_response: NodeGet | NodeGetIdle | DynamicServiceGet
) -> None:
    mocked_rpc_client = AsyncMock()
    mocked_rpc_client.request = AsyncMock(return_value=expected_response)
    mocker.patch(
        "simcore_service_webserver.dynamic_scheduler._rpc.get_rabbitmq_rpc_client",
        return_value=mocked_rpc_client,
    )


@pytest.fixture
def rpc_dynamic_service_create() -> RPCDynamicServiceCreate:
    return RPCDynamicServiceCreate.parse_obj(
        RPCDynamicServiceCreate.Config.schema_extra["example"]
    )


@pytest.mark.parametrize(
    "expected_response",
    [
        NodeGet.parse_obj(NodeGet.Config.schema_extra["example"]),
        NodeGetIdle.parse_obj(NodeGetIdle.Config.schema_extra["example"]),
        DynamicServiceGet.parse_obj(
            DynamicServiceGet.Config.schema_extra["examples"][0]
        ),
    ],
)
async def test_get_service_status(
    mock_rpc_client: None,
    mocked_app: AsyncMock,
    node_id: NodeID,
    expected_response: NodeGet | NodeGetIdle | DynamicServiceGet,
):
    assert await get_dynamic_service(mocked_app, node_id=node_id) == expected_response


@pytest.mark.parametrize(
    "expected_response",
    [
        NodeGet.parse_obj(NodeGet.Config.schema_extra["example"]),
        DynamicServiceGet.parse_obj(
            DynamicServiceGet.Config.schema_extra["examples"][0]
        ),
    ],
)
async def test_run_dynamic_service(
    mock_rpc_client: None,
    mocked_app: AsyncMock,
    expected_response: NodeGet | NodeGetIdle | DynamicServiceGet,
    rpc_dynamic_service_create: RPCDynamicServiceCreate,
):
    assert (
        await run_dynamic_service(
            mocked_app, rpc_dynamic_service_create=rpc_dynamic_service_create
        )
        == expected_response
    )
