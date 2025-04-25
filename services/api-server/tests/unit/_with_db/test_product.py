# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import datetime
from collections.abc import AsyncGenerator, Callable
from decimal import Decimal

import httpx
import respx
from faker import Faker
from fastapi import status
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_api_server.api_keys import ApiKeyInDB
from models_library.generics import Envelope
from models_library.wallets import WalletStatus
from pydantic import PositiveInt
from pytest_mock import MockType
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.schemas.model_adapter import (
    WalletGetWithAvailableCreditsLegacy,
)


async def test_product_webserver(
    client: httpx.AsyncClient,
    mocked_webserver_rest_api_base: respx.MockRouter,
    create_fake_api_keys: Callable[[PositiveInt], AsyncGenerator[ApiKeyInDB, None]],
    faker: Faker,
):
    assert client

    wallet_to_api_keys_map: dict[int, ApiKeyInDB] = {}
    wallet_id: int = faker.pyint(min_value=1)
    async for api_key in create_fake_api_keys(2):
        wallet_id += faker.pyint(min_value=1)
        wallet_to_api_keys_map[wallet_id] = api_key

    def _check_key_product_compatibility(request: httpx.Request, **kwargs):
        assert (
            received_product_name := request.headers.get("x-simcore-products-name")
        ) is not None
        assert (wallet_id := kwargs.get("wallet_id")) is not None
        assert (api_key := wallet_to_api_keys_map[int(wallet_id)]) is not None
        assert api_key.product_name == received_product_name
        return httpx.Response(
            status.HTTP_200_OK,
            json=jsonable_encoder(
                Envelope[WalletGetWithAvailableCreditsLegacy](
                    data=WalletGetWithAvailableCreditsLegacy(
                        wallet_id=wallet_id,
                        name="my_wallet",
                        description="this is my wallet",
                        owner=api_key.id_,
                        thumbnail="something",
                        status=WalletStatus.ACTIVE,
                        created=datetime.datetime.now(),
                        modified=datetime.datetime.now(),
                        available_credits=Decimal(20.0),
                    )
                )
            ),
        )

    wallet_get_mock = mocked_webserver_rest_api_base.get(
        path__regex=r"/wallets/(?P<wallet_id>[-+]?\d+)"
    ).mock(side_effect=_check_key_product_compatibility)

    for wallet_id, api_key in wallet_to_api_keys_map.items():
        response = await client.get(
            f"{API_VTAG}/wallets/{wallet_id}",
            auth=httpx.BasicAuth(api_key.api_key, api_key.api_secret),
        )
        assert response.status_code == status.HTTP_200_OK
    assert wallet_get_mock.call_count == len(wallet_to_api_keys_map)


async def test_product_catalog(
    client: httpx.AsyncClient,
    mocked_catalog_rpc_api: dict[str, MockType],
    create_fake_api_keys: Callable[[PositiveInt], AsyncGenerator[ApiKeyInDB, None]],
):
    assert client

    valid_api_auths: list[ApiKeyInDB] = [key async for key in create_fake_api_keys(2)]
    assert len({key.product_name for key in valid_api_auths}) == 2

    for api_auth in valid_api_auths:
        await client.get(
            f"{API_VTAG}/solvers/simcore/services/comp/isolve/releases/2.0.24",
            auth=httpx.BasicAuth(api_auth.api_key, api_auth.api_secret),
        )

    assert mocked_catalog_rpc_api["get_service"].called
