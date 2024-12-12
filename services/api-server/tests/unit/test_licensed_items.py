import pytest
from fastapi import status
from httpx import AsyncClient, BasicAuth
from models_library.api_schemas_webserver.licensed_items import LicensedItemGetPage
from pytest_mock import MockerFixture
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from simcore_service_api_server._meta import API_VTAG


@pytest.fixture
async def mock_wb_api_server_rcp(mocker: MockerFixture) -> MockerFixture:
    async def _get_backend_licensed_items(
        rabbitmq_rpc_client: RabbitMQRPCClient,
        *,
        product_name: str,
        offset: int,
        limit: int,
    ) -> LicensedItemGetPage:
        return None

    mocker.patch(
        "servicelib.rabbitmq.rpc_interfaces.webserver.licenses.licensed_items.get_licensed_items",
        _get_backend_licensed_items,
    )

    return mocker


async def test_get_licensed_items(
    mock_wb_api_server_rcp: MockerFixture, client: AsyncClient, auth: BasicAuth
):

    resp = await client.get(f"{API_VTAG}/credits/price", auth=auth)
    assert resp.status_code == status.HTTP_200_OK
