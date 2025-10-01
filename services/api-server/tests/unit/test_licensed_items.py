# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import asyncio
from collections.abc import Callable
from typing import Any, Protocol, cast
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
from pytest_mock import MockerFixture, MockType
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


@pytest.fixture
async def mock_wb_api_server_rcp(app: FastAPI, mocker: MockerFixture) -> None:
    def _new():
        from simcore_service_api_server.services_rpc import wb_api_server

        # pylint: disable=protected-access
        return wb_api_server._create_obj(
            app, mocker.MagicMock(spec=RabbitMQRPCClient)
        )  # noqa: SLF001

    app.dependency_overrides[get_wb_api_rpc_client] = _new


@pytest.fixture
async def mock_rut_rpc(app: FastAPI, mocker: MockerFixture) -> None:
    app.dependency_overrides[get_resource_usage_tracker_client] = (
        lambda: ResourceUsageTrackerClient(
            _client=mocker.MagicMock(spec=RabbitMQRPCClient)
        )
    )


class HandlerMockFactory(Protocol):
    def __call__(
        self,
        handler_name: str = "",
        return_value: Any = None,
        exception: Exception | None = None,
        side_effect: Callable | None = None,
    ) -> MockType: ...


@pytest.fixture()
def mock_handler_in_licenses_rpc_interface(
    mock_wb_api_server_rcp: None,
    mocker: MockerFixture,
) -> HandlerMockFactory:
    """Factory to mock a handler in the LicensesRpcApi interface"""

    def _create(
        handler_name: str = "",
        return_value: Any = None,
        exception: Exception | None = None,
        side_effect: Callable | None = None,
    ) -> MockType:
        from servicelib.rabbitmq.rpc_interfaces.webserver.v1.licenses import (
            LicensesRpcApi,
        )

        assert exception is None or side_effect is None

        return mocker.patch.object(
            LicensesRpcApi,
            handler_name,
            return_value=return_value,
            side_effect=exception or side_effect,
        )

    return _create


async def test_get_licensed_items(
    mock_handler_in_licenses_rpc_interface: HandlerMockFactory,
    client: AsyncClient,
    auth: BasicAuth,
):
    async def _get_licensed_items_side_effect(
        product_name: str,
        offset: int,
        limit: int,
    ) -> LicensedItemRpcGetPage:
        examples = LicensedItemRpcGet.model_json_schema()["examples"]
        assert isinstance(examples, list)
        return LicensedItemRpcGetPage(
            items=[LicensedItemRpcGet.model_validate(ex) for ex in examples],
            total=len(examples),
        )

    mock_handler_in_licenses_rpc_interface(
        handler_name="get_licensed_items",
        side_effect=_get_licensed_items_side_effect,
    )

    resp = await client.get(f"{API_VTAG}/licensed-items", auth=auth)
    assert resp.status_code == status.HTTP_200_OK
    TypeAdapter(Page[LicensedItemGet]).validate_json(resp.text)


async def test_get_licensed_items_timeout(
    mock_handler_in_licenses_rpc_interface: HandlerMockFactory,
    client: AsyncClient,
    auth: BasicAuth,
):
    mock_handler_in_licenses_rpc_interface(
        handler_name="get_licensed_items",
        exception=TimeoutError(),
    )

    resp = await client.get(f"{API_VTAG}/licensed-items", auth=auth)
    assert resp.status_code == status.HTTP_504_GATEWAY_TIMEOUT


@pytest.mark.parametrize(
    "exception_to_raise",
    [asyncio.CancelledError(), RuntimeError(), RemoteMethodNotRegisteredError()],
)
async def test_get_licensed_items_502(
    mock_handler_in_licenses_rpc_interface: HandlerMockFactory,
    client: AsyncClient,
    auth: BasicAuth,
    exception_to_raise: Exception,
):
    mock_handler_in_licenses_rpc_interface(
        handler_name="get_licensed_items",
        exception=exception_to_raise,
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
    mock_handler_in_licenses_rpc_interface: HandlerMockFactory,
    client: AsyncClient,
    auth: BasicAuth,
    exception_to_raise: Exception | None,
    expected_api_server_status_code: int,
    faker: Faker,
):
    _wallet_id = faker.pyint(min_value=1)

    async def _side_effect(
        product_name: str,
        wallet_id: WalletID,
        user_id: UserID,
        offset: int,
        limit: int,
    ) -> LicensedItemRpcGetPage:

        if exception_to_raise is not None:
            raise exception_to_raise

        assert _wallet_id == wallet_id
        if exception_to_raise is not None:
            raise exception_to_raise

        examples = LicensedItemRpcGet.model_json_schema()["examples"]
        assert isinstance(examples, list)
        return LicensedItemRpcGetPage(
            items=[LicensedItemRpcGet.model_validate(ex) for ex in examples],
            total=len(examples),
        )

    mock_handler_in_licenses_rpc_interface(
        handler_name="get_available_licensed_items_for_wallet",
        side_effect=_side_effect,
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
    mock_handler_in_licenses_rpc_interface: HandlerMockFactory,
    client: AsyncClient,
    auth: BasicAuth,
    exception_to_raise: Exception | None,
    expected_api_server_status_code: int,
    faker: Faker,
):
    _wallet_id = faker.pyint(min_value=1)
    _licensed_item_id = faker.uuid4()

    async def _side_effect(
        product_name: str,
        user_id: UserID,
        wallet_id: WalletID,
        licensed_item_id: LicensedItemID,
        num_of_seats: int,
        service_run_id: ServiceRunID,
    ) -> LicensedItemCheckoutRpcGet:
        if exception_to_raise is not None:
            raise exception_to_raise

        examples = LicensedItemCheckoutRpcGet.model_json_schema()["examples"]
        assert isinstance(examples, list)
        assert len(examples) > 0
        example = examples[0]
        assert isinstance(example, dict)
        return LicensedItemCheckoutRpcGet.model_validate(example)

    mock_handler_in_licenses_rpc_interface(
        handler_name="checkout_licensed_item_for_wallet",
        side_effect=_side_effect,
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
    mock_handler_in_licenses_rpc_interface: HandlerMockFactory,
    mock_rut_rpc: None,
    mocker: MockerFixture,
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

    # mocks PRC to -> RUT (NOTE: this is old style RPC client!)
    async def _get_licensed_item_checkout_side_effect(
        rabbitmq_rpc_client: RabbitMQRPCClient,
        product_name: str,
        licensed_item_checkout_id: LicensedItemCheckoutID,
    ) -> LicensedItemCheckoutGet:
        if rut_exception_to_raise is not None:
            raise rut_exception_to_raise

        examples = LicensedItemCheckoutGet.model_json_schema()["examples"]
        assert isinstance(examples, list)
        assert len(examples) > 0
        example = examples[0]
        assert isinstance(example, dict)
        licensed_item_checkout_get = LicensedItemCheckoutGet.model_validate(example)
        if valid_license_checkout_id:
            licensed_item_checkout_get.licensed_item_id = _licensed_item_id
        return licensed_item_checkout_get

    mocker.patch(
        "simcore_service_api_server.services_rpc.resource_usage_tracker._get_licensed_item_checkout",
        _get_licensed_item_checkout_side_effect,
    )

    # mocks RPC to -> wb-api-server
    async def _release_licensed_item_for_wallet_side_effect(
        product_name: str,
        user_id: int,
        licensed_item_checkout_id: LicensedItemCheckoutID,
    ) -> LicensedItemCheckoutRpcGet:
        if wb_api_exception_to_raise is not None:
            raise wb_api_exception_to_raise

        examples = LicensedItemCheckoutRpcGet.model_json_schema()["examples"]
        assert isinstance(examples, list)
        assert len(examples) > 0
        example = examples[0]
        assert isinstance(example, dict)
        return LicensedItemCheckoutRpcGet.model_validate(example)

    mock_handler_in_licenses_rpc_interface(
        handler_name="release_licensed_item_for_wallet",
        side_effect=_release_licensed_item_for_wallet_side_effect,
    )

    # TEST
    resp = await client.post(
        f"{API_VTAG}/licensed-items/{_licensed_item_id}/checked-out-items/{_licensed_item_checkout_id}/release",
        auth=auth,
    )

    # ASSERT
    assert resp.status_code == expected_api_server_status_code
