# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
import asyncio

import pytest
from fastapi import status
from httpx import AsyncClient, BasicAuth
from models_library.api_schemas_webserver.licensed_items import (
    LicensedItemGet as _LicensedItemGet,
)
from models_library.api_schemas_webserver.licensed_items import (
    LicensedItemGetPage as _LicensedItemGetPage,
)
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq._errors import RemoteMethodNotRegisteredError
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.pagination import Page
from simcore_service_api_server.models.schemas.model_adapter import LicensedItemGet


@pytest.fixture
async def mock_rabbitmq_rpc_client(mocker: MockerFixture) -> MockerFixture:
    class DummyRabbitMqRpcClient:
        pass

    def _get_dummy_rpc_client():
        return DummyRabbitMqRpcClient

    mocker.patch(
        "simcore_service_api_server.core.application.get_rabbitmq_rpc_client",
        sideeffect=_get_dummy_rpc_client,
    )
    return mocker


@pytest.fixture
async def mock_wb_api_server_rcp(
    mock_rabbitmq_rpc_client: MockerFixture, exception_to_raise: Exception | None
) -> MockerFixture:
    async def _get_backend_licensed_items(
        rabbitmq_rpc_client: RabbitMQRPCClient,
        *,
        product_name: str,
        offset: int,
        limit: int,
    ) -> _LicensedItemGetPage:
        if exception_to_raise is not None:
            raise exception_to_raise
        extra = _LicensedItemGet.model_config.get("json_schema_extra")
        assert isinstance(extra, dict)
        examples = extra.get("examples")
        assert isinstance(examples, list)
        return _LicensedItemGetPage(
            items=[_LicensedItemGet.model_validate(ex) for ex in examples],
            total=len(examples),
        )

    mock_rabbitmq_rpc_client.patch(
        "simcore_service_api_server.services_rpc.wb_api_server._get_licensed_items",
        _get_backend_licensed_items,
    )

    return mock_rabbitmq_rpc_client


@pytest.mark.parametrize("exception_to_raise", [None])
async def test_get_licensed_items(
    mock_wb_api_server_rcp: MockerFixture, client: AsyncClient, auth: BasicAuth
):
    resp = await client.get(f"{API_VTAG}/licensed-items", auth=auth)
    assert resp.status_code == status.HTTP_200_OK
    TypeAdapter(Page[LicensedItemGet]).validate_json(resp.text)


@pytest.mark.parametrize("exception_to_raise", [asyncio.TimeoutError()])
async def test_get_licensed_items_timeout(
    mock_wb_api_server_rcp: MockerFixture, client: AsyncClient, auth: BasicAuth
):
    resp = await client.get(f"{API_VTAG}/licensed-items", auth=auth)
    assert resp.status_code == status.HTTP_504_GATEWAY_TIMEOUT


@pytest.mark.parametrize(
    "exception_to_raise",
    [asyncio.CancelledError(), RuntimeError(), RemoteMethodNotRegisteredError()],
)
async def test_get_licensed_items_502(
    mock_wb_api_server_rcp: MockerFixture, client: AsyncClient, auth: BasicAuth
):
    resp = await client.get(f"{API_VTAG}/licensed-items", auth=auth)
    assert resp.status_code == status.HTTP_502_BAD_GATEWAY
