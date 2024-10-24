# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from unittest.mock import AsyncMock

import pytest
from faker import Faker
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
)
from models_library.api_schemas_webserver.projects_nodes import (
    NodeGet,
    NodeGetIdle,
    NodeGetUnknown,
)
from models_library.projects_nodes_io import NodeID
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RPCServerError
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
        "simcore_service_webserver.dynamic_scheduler.api.get_rabbitmq_rpc_client",
        return_value=mocked_rpc_client,
    )


@pytest.fixture
def dynamic_service_start() -> DynamicServiceStart:
    return DynamicServiceStart.model_validate(
        DynamicServiceStart.model_config["json_schema_extra"]["example"]
    )


@pytest.mark.parametrize(
    "expected_response",
    [
        *[
            NodeGet.model_validate(x)
            for x in NodeGet.model_config["json_schema_extra"]["examples"]
        ],
        NodeGetIdle.model_validate(
            NodeGetIdle.model_config["json_schema_extra"]["example"]
        ),
        DynamicServiceGet.model_validate(
            DynamicServiceGet.model_config["json_schema_extra"]["examples"][0]
        ),
    ],
)
async def test_get_service_status(
    mock_rpc_client: None,
    mocked_app: AsyncMock,
    node_id: NodeID,
    expected_response: NodeGet | NodeGetIdle | NodeGetUnknown | DynamicServiceGet,
):
    assert await get_dynamic_service(mocked_app, node_id=node_id) == expected_response


async def test_get_service_status_raises_rpc_server_error(
    mocker: MockerFixture, mocked_app: AsyncMock, node_id: NodeID
):
    mocked_rpc_client = AsyncMock()

    exc = RuntimeError("a_custom_message")
    mocked_rpc_client.request = AsyncMock(
        side_effect=RPCServerError(
            exc_type=f"{exc.__class__.__module__}.{exc.__class__.__name__}",
            exc_message=f"{exc}",
            method_name="test",
            traceback="test",
        )
    )
    mocker.patch(
        "simcore_service_webserver.dynamic_scheduler.api.get_rabbitmq_rpc_client",
        return_value=mocked_rpc_client,
    )

    assert await get_dynamic_service(
        mocked_app, node_id=node_id
    ) == NodeGetUnknown.from_node_id(node_id)


@pytest.mark.parametrize(
    "expected_response",
    [
        *[
            NodeGet.model_validate(x)
            for x in NodeGet.model_config["json_schema_extra"]["examples"]
        ],
        DynamicServiceGet.model_validate(
            DynamicServiceGet.model_config["json_schema_extra"]["examples"][0]
        ),
    ],
)
async def test_run_dynamic_service(
    mock_rpc_client: None,
    mocked_app: AsyncMock,
    expected_response: NodeGet | NodeGetIdle | DynamicServiceGet,
    dynamic_service_start: DynamicServiceStart,
):
    assert (
        await run_dynamic_service(
            mocked_app, dynamic_service_start=dynamic_service_start
        )
        == expected_response
    )
