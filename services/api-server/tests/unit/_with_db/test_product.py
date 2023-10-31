import datetime
from decimal import Decimal
from typing import AsyncGenerator, Callable

import httpx
import respx
from faker import Faker
from fastapi import status
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_webserver.wallets import WalletGetWithAvailableCredits
from models_library.generics import Envelope
from models_library.wallets import WalletStatus
from pydantic import PositiveInt
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.domain.api_keys import ApiKeyInDB


async def test_product_webserver(
    client: httpx.AsyncClient,
    mocked_webserver_service_api_base: respx.MockRouter,
    fake_api_keys: Callable[[PositiveInt], AsyncGenerator[ApiKeyInDB, None]],
    faker: Faker,
) -> None:
    assert client

    keys: dict[int, ApiKeyInDB] = {}
    wallet_id: int = faker.pyint(min_value=1)
    async for key in fake_api_keys(2):
        wallet_id += faker.pyint(min_value=1)
        keys[wallet_id] = key

    def _check_key_product_compatibility(request: httpx.Request, **kwargs):
        assert (
            received_product_name := request.headers.get("x-simcore-products-name")
        ) is not None
        assert (wallet_id := kwargs.get("wallet_id")) is not None
        assert (key := keys[int(wallet_id)]) is not None
        assert key.product_name == received_product_name
        return httpx.Response(
            status.HTTP_200_OK,
            json=jsonable_encoder(
                Envelope[WalletGetWithAvailableCredits](
                    data=WalletGetWithAvailableCredits(
                        wallet_id=wallet_id,
                        name="my_wallet",
                        description="this is my wallet",
                        owner=key.id_,
                        thumbnail="something",
                        status=WalletStatus.ACTIVE,
                        created=datetime.datetime.now(),
                        modified=datetime.datetime.now(),
                        available_credits=Decimal(20.0),
                    )
                )
            ),
        )

    wallet_get_mock = mocked_webserver_service_api_base.get(
        path__regex=r"/wallets/(?P<wallet_id>[-+]?\d+)"
    ).mock(side_effect=_check_key_product_compatibility)

    for wallet_id in keys:
        key = keys[wallet_id]
        response = await client.get(
            f"{API_VTAG}/wallets/{wallet_id}",
            auth=httpx.BasicAuth(key.api_key, key.api_secret.get_secret_value()),
        )
        assert response.status_code == status.HTTP_200_OK
    assert wallet_get_mock.call_count == len(keys)


async def test_product_catalog(
    client: httpx.AsyncClient,
    mocked_catalog_service_api_base: respx.MockRouter,
    fake_api_keys: Callable[[PositiveInt], AsyncGenerator[ApiKeyInDB, None]],
) -> None:
    assert client

    keys: list[ApiKeyInDB] = [key async for key in fake_api_keys(2)]
    assert len({key.product_name for key in keys}) == 2

    def _get_service_side_effect(request: httpx.Request, **kwargs):
        assert (
            received_product := request.headers.get("x-simcore-products-name")
        ) is not None
        assert (
            user_id := dict(
                elm.split("=") for elm in request.url.query.decode().split("&")
            ).get("user_id")
        ) is not None
        key: ApiKeyInDB | None = None
        for key in keys:
            if key.id_ == int(user_id):
                break
        assert key is not None
        assert key.product_name == received_product
        return httpx.Response(status_code=status.HTTP_200_OK)

    respx_mock = mocked_catalog_service_api_base.get(
        r"/v0/services/simcore%2Fservices%2Fcomp%2Fisolve/2.0.24"
    ).mock(side_effect=_get_service_side_effect)

    for key in keys:
        response = await client.get(
            f"{API_VTAG}/solvers/simcore/services/comp/isolve/releases/2.0.24",
            auth=httpx.BasicAuth(key.api_key, key.api_secret.get_secret_value()),
        )

    assert respx_mock.call_count == len(keys)
