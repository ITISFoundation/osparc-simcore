# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
import asyncio
from functools import partial

import pytest
from faker import Faker
from fastapi import FastAPI, status
from httpx import AsyncClient, BasicAuth
from models_library.api_schemas_webserver.licensed_items import (
    LicensedItemGet as _LicensedItemGet,
)
from models_library.api_schemas_webserver.licensed_items import (
    LicensedItemGetPage as _LicensedItemGetPage,
)
from models_library.api_schemas_webserver.licensed_items_checkouts import (
    LicensedItemCheckoutRpcGet,
)
from models_library.licensed_items import LicensedItemID
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq._errors import RemoteMethodNotRegisteredError
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.api.dependencies.webserver_rpc import (
    get_wb_api_rpc_client,
)
from simcore_service_api_server.models.pagination import Page
from simcore_service_api_server.models.schemas.licensed_items import (
    LicensedItemCheckoutData,
)
from simcore_service_api_server.models.schemas.model_adapter import LicensedItemGet
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient


async def _get_backend_licensed_items(
    exception_to_raise: Exception | None,
    rabbitmq_rpc_client: RabbitMQRPCClient,
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


@pytest.fixture
async def mock_wb_api_server_rcp(app: FastAPI, mocker: MockerFixture) -> MockerFixture:
    class DummyRpcClient:
        pass

    app.dependency_overrides[get_wb_api_rpc_client] = lambda: WbApiRpcClient(
        _client=DummyRpcClient()
    )
    return mocker


async def test_get_licensed_items(
    mock_wb_api_server_rcp: MockerFixture, client: AsyncClient, auth: BasicAuth
):
    mock_wb_api_server_rcp.patch(
        "simcore_service_api_server.services_rpc.wb_api_server._get_licensed_items",
        partial(_get_backend_licensed_items, None),
    )
    resp = await client.get(f"{API_VTAG}/licensed-items", auth=auth)
    assert resp.status_code == status.HTTP_200_OK
    TypeAdapter(Page[LicensedItemGet]).validate_json(resp.text)


async def test_get_licensed_items_timeout(
    mock_wb_api_server_rcp: MockerFixture, client: AsyncClient, auth: BasicAuth
):
    mock_wb_api_server_rcp.patch(
        "simcore_service_api_server.services_rpc.wb_api_server._get_licensed_items",
        partial(_get_backend_licensed_items, exception_to_raise=asyncio.TimeoutError()),
    )
    resp = await client.get(f"{API_VTAG}/licensed-items", auth=auth)
    assert resp.status_code == status.HTTP_504_GATEWAY_TIMEOUT


@pytest.mark.parametrize(
    "exception_to_raise",
    [asyncio.CancelledError(), RuntimeError(), RemoteMethodNotRegisteredError()],
)
async def test_get_licensed_items_502(
    mock_wb_api_server_rcp: MockerFixture,
    client: AsyncClient,
    auth: BasicAuth,
    exception_to_raise: Exception,
):
    mock_wb_api_server_rcp.patch(
        "simcore_service_api_server.services_rpc.wb_api_server._get_licensed_items",
        partial(_get_backend_licensed_items, exception_to_raise),
    )
    resp = await client.get(f"{API_VTAG}/licensed-items", auth=auth)
    assert resp.status_code == status.HTTP_502_BAD_GATEWAY


@pytest.mark.parametrize(
    "exception_to_raise,expected_api_server_status_code",
    [
        (NotImplementedError(), status.HTTP_501_NOT_IMPLEMENTED),
    ],
)
async def test_get_licensed_items_for_wallet(
    mock_wb_api_server_rcp: MockerFixture,
    client: AsyncClient,
    auth: BasicAuth,
    exception_to_raise: Exception | None,
    expected_api_server_status_code: int,
    faker: Faker,
):
    _wallet_id = faker.pyint(min_value=1)

    async def side_effect(
        rabbitmq_rpc_client: RabbitMQRPCClient,
        product_name: str,
        wallet_id: WalletID,
        user_id: UserID,
        offset: int,
        limit: int,
    ) -> _LicensedItemGetPage:
        assert _wallet_id == wallet_id
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

    mock_wb_api_server_rcp.patch(
        "simcore_service_api_server.services_rpc.wb_api_server._get_available_licensed_items_for_wallet",
        side_effect,
    )
    resp = await client.get(
        f"{API_VTAG}/wallets/{_wallet_id}/licensed-items", auth=auth
    )
    assert resp.status_code == expected_api_server_status_code


@pytest.mark.parametrize(
    "exception_to_raise,expected_api_server_status_code",
    [
        (None, status.HTTP_200_OK),
    ],
)
async def test_get_licensed_items_checkout(
    mock_wb_api_server_rcp: MockerFixture,
    client: AsyncClient,
    auth: BasicAuth,
    exception_to_raise: Exception | None,
    expected_api_server_status_code: int,
    faker: Faker,
):
    _wallet_id = faker.pyint(min_value=1)
    _licensed_item_id = faker.uuid4()

    async def side_effect(
        rabbitmq_rpc_client: RabbitMQRPCClient,
        product_name: str,
        user_id: UserID,
        wallet_id: WalletID,
        licensed_item_id: LicensedItemID,
        num_of_seats: int,
        service_run_id: ServiceRunID,
    ) -> LicensedItemCheckoutRpcGet:
        if exception_to_raise is not None:
            raise exception_to_raise
        extra = LicensedItemCheckoutRpcGet.model_config.get("json_schema_extra")
        assert isinstance(extra, dict)
        examples = extra.get("examples")
        assert isinstance(examples, list)
        assert len(examples) > 0
        example = examples[0]
        assert isinstance(example, dict)
        return LicensedItemCheckoutRpcGet.model_validate(example)

    mock_wb_api_server_rcp.patch(
        "simcore_service_api_server.services_rpc.wb_api_server._checkout_licensed_item_for_wallet",
        side_effect,
    )
    body = LicensedItemCheckoutData(
        number_of_seats=faker.pyint(min_value=1), service_run_id="myservice"
    )
    resp = await client.post(
        f"{API_VTAG}/wallets/{_wallet_id}/licensed-items/{_licensed_item_id}/checkout",
        auth=auth,
        content=body.model_dump_json(),
    )
    assert resp.status_code == expected_api_server_status_code
