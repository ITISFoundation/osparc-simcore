from typing import Any, Final, cast
from uuid import UUID, uuid5

from aiocache import cached
from fastapi import FastAPI
from models_library.api_schemas_webserver.auth import ApiKeyGet
from models_library.products import ProductName
from models_library.users import UserID

from ._api_auth_rpc import create_api_key_and_secret, get_api_key_and_secret

_NAMESPACE: Final = UUID("ce021d45-82e6-4dfe-872c-2f452cf289f8")


def _create_unique_identifier_from(*parts: Any) -> str:
    return f"{uuid5(_NAMESPACE, '/'.join(map(str, parts)) )}"


def create_user_api_name(product_name: ProductName, user_id: UserID) -> str:
    return f"__auto_{_create_unique_identifier_from(product_name, user_id)}"


def _build_cache_key(fct, *_, **kwargs):
    return f"{fct.__name__}_{kwargs['product_name']}_{kwargs['user_id']}"


@cached(ttl=3, key_builder=_build_cache_key)
async def _get_or_create_data(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
) -> ApiKeyGet:

    name = create_user_api_name(product_name, user_id)
    if data := await get_api_key_and_secret(
        app, product_name=product_name, user_id=user_id, name=name
    ):
        return data
    return await create_api_key_and_secret(
        app, product_name=product_name, user_id=user_id, name=name, expiration=None
    )


async def get_or_create_user_api_key(
    app: FastAPI,
    product_name: ProductName,
    user_id: UserID,
) -> str:
    data = await _get_or_create_data(
        app,
        product_name=product_name,
        user_id=user_id,
    )
    return cast(str, data.api_key)


async def get_or_create_user_api_secret(
    app: FastAPI,
    product_name: ProductName,
    user_id: UserID,
) -> str:
    data = await _get_or_create_data(
        app,
        product_name=product_name,
        user_id=user_id,
    )
    return cast(str, data.api_secret)


__all__: tuple[str, ...] = (
    "get_or_create_user_api_key",
    "get_or_create_user_api_secret",
    "create_user_api_name",
)
