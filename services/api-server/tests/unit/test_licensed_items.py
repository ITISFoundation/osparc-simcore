# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
import asyncio
from functools import partial
from typing import cast
from uuid import UUID

import pytest
from faker import Faker
from fastapi import FastAPI, status
from httpx import AsyncClient, BasicAuth
from models_library.api_schemas_resource_usage_tracker.licensed_items_checkouts import (
    LicensedItemCheckoutGet,
)
from models_library.api_schemas_webserver.licensed_items import (
    LicensedItemRpcGet,
    LicensedItemRpcGetPage,
)
from models_library.api_schemas_webserver.licensed_items_checkouts import (
    LicensedItemCheckoutRpcGet,
)
from models_library.licenses import LicensedItemID
from models_library.resource_tracker_licensed_items_checkouts import (
    LicensedItemCheckoutID,
)
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq._errors import RemoteMethodNotRegisteredError
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    CanNotCheckoutNotEnoughAvailableSeatsError,
    CanNotCheckoutServiceIsNotRunningError,
    LicensedItemCheckoutNotFoundError,
    NotEnoughAvailableSeatsError,
)
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.api.dependencies.resource_usage_tracker_rpc import (
    get_resource_usage_tracker_client,
)
from simcore_service_api_server.api.dependencies.webserver_rpc import (
    get_wb_api_rpc_client,
)
from simcore_service_api_server.models.pagination import Page
from simcore_service_api_server.models.schemas.licensed_items import (
    LicensedItemCheckoutData,
)
from simcore_service_api_server.models.schemas.model_adapter import LicensedItemGet
from simcore_service_api_server.services_rpc.resource_usage_tracker import (
    ResourceUsageTrackerClient,
)
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient


async def _get_backend_licensed_items(
    exception_to_raise: Exception | None,
    rabbitmq_rpc_client: RabbitMQRPCClient,
    product_name: str,
    offset: int,
    limit: int,
) -> LicensedItemRpcGetPage:
    if exception_to_raise is not None:
        raise exception_to_raise
    extra = LicensedItemRpcGet.model_config.get("json_schema_extra")
    assert isinstance(extra, dict)
    examples = extra.get("examples")
    assert isinstance(examples, list)
    return LicensedItemRpcGetPage(
        items=[LicensedItemRpcGet.model_validate(ex) for ex in examples],
        total=len(examples),
    )


@pytest.fixture
async def mock_wb_api_server_rcp(app: FastAPI, mocker: MockerFixture) -> MockerFixture:
    from servicelib.rabbitmq.rpc_interfaces.webserver.v1 import WebServerRpcClient

    app.dependency_overrides[get_wb_api_rpc_client] = lambda: WbApiRpcClient(
        _client=mocker.MagicMock(spec=RabbitMQRPCClient),
        _rpc_client=mocker.MagicMock(spec=WebServerRpcClient),
    )
    return mocker


@pytest.fixture
async def mock_rut_rpc(app: FastAPI, mocker: MockerFixture) -> MockerFixture:
    app.dependency_overrides[get_resource_usage_tracker_client] = (
        lambda: ResourceUsageTrackerClient(
            _client=mocker.MagicMock(spec=RabbitMQRPCClient)
        )
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
        partial(_get_backend_licensed_items, exception_to_raise=TimeoutError()),
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
    ) -> LicensedItemRpcGetPage:
        assert _wallet_id == wallet_id
        if exception_to_raise is not None:
            raise exception_to_raise
        extra = LicensedItemRpcGet.model_config.get("json_schema_extra")
        assert isinstance(extra, dict)
        examples = extra.get("examples")
        assert isinstance(examples, list)
        return LicensedItemRpcGetPage(
            items=[LicensedItemRpcGet.model_validate(ex) for ex in examples],
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
        (NotEnoughAvailableSeatsError(), status.HTTP_409_CONFLICT),
        (CanNotCheckoutNotEnoughAvailableSeatsError(), status.HTTP_409_CONFLICT),
        (
            CanNotCheckoutServiceIsNotRunningError(),
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
    ],
)
async def test_checkout_licensed_item(
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
        number_of_seats=faker.pyint(min_value=1),
        service_run_id=cast(ServiceRunID, "myservice"),
    )
    resp = await client.post(
        f"{API_VTAG}/wallets/{_wallet_id}/licensed-items/{_licensed_item_id}/checkout",
        auth=auth,
        content=body.model_dump_json(),
    )
    assert resp.status_code == expected_api_server_status_code


@pytest.mark.parametrize(
    "wb_api_exception_to_raise,rut_exception_to_raise,expected_api_server_status_code,valid_license_checkout_id",
    [
        (LicensedItemCheckoutNotFoundError, None, status.HTTP_404_NOT_FOUND, True),
        (None, LicensedItemCheckoutNotFoundError, status.HTTP_404_NOT_FOUND, True),
        (None, None, status.HTTP_200_OK, True),
        (None, None, status.HTTP_422_UNPROCESSABLE_ENTITY, False),
    ],
)
async def test_release_checked_out_licensed_item(
    mock_wb_api_server_rcp: MockerFixture,
    mock_rut_rpc: MockerFixture,
    client: AsyncClient,
    auth: BasicAuth,
    wb_api_exception_to_raise: Exception | None,
    rut_exception_to_raise: Exception | None,
    expected_api_server_status_code: int,
    valid_license_checkout_id: bool,
    faker: Faker,
):
    _licensed_item_id = cast(UUID, faker.uuid4())
    _licensed_item_checkout_id = cast(UUID, faker.uuid4())

    async def get_licensed_item_checkout(
        rabbitmq_rpc_client: RabbitMQRPCClient,
        product_name: str,
        licensed_item_checkout_id: LicensedItemCheckoutID,
    ) -> LicensedItemCheckoutGet:
        if rut_exception_to_raise is not None:
            raise rut_exception_to_raise
        extra = LicensedItemCheckoutGet.model_config.get("json_schema_extra")
        assert isinstance(extra, dict)
        examples = extra.get("examples")
        assert isinstance(examples, list)
        assert len(examples) > 0
        example = examples[0]
        assert isinstance(example, dict)
        licensed_item_checkout_get = LicensedItemCheckoutGet.model_validate(example)
        if valid_license_checkout_id:
            licensed_item_checkout_get.licensed_item_id = _licensed_item_id
        return licensed_item_checkout_get

    async def release_licensed_item_for_wallet(
        rabbitmq_rpc_client: RabbitMQRPCClient,
        product_name: str,
        user_id: int,
        licensed_item_checkout_id: LicensedItemCheckoutID,
    ) -> LicensedItemCheckoutRpcGet:
        if wb_api_exception_to_raise is not None:
            raise wb_api_exception_to_raise
        extra = LicensedItemCheckoutRpcGet.model_config.get("json_schema_extra")
        assert isinstance(extra, dict)
        examples = extra.get("examples")
        assert isinstance(examples, list)
        assert len(examples) > 0
        example = examples[0]
        assert isinstance(example, dict)
        return LicensedItemCheckoutRpcGet.model_validate(example)

    mock_rut_rpc.patch(
        "simcore_service_api_server.services_rpc.resource_usage_tracker._get_licensed_item_checkout",
        get_licensed_item_checkout,
    )
    mock_wb_api_server_rcp.patch(
        "simcore_service_api_server.services_rpc.wb_api_server._release_licensed_item_for_wallet",
        release_licensed_item_for_wallet,
    )

    resp = await client.post(
        f"{API_VTAG}/licensed-items/{_licensed_item_id}/checked-out-items/{_licensed_item_checkout_id}/release",
        auth=auth,
    )
    assert resp.status_code == expected_api_server_status_code
