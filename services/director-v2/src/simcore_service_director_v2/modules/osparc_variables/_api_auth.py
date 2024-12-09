import uuid
from typing import cast
from uuid import uuid5

from aiocache import cached  # type: ignore[import-untyped]
from fastapi import FastAPI
from models_library.products import ProductName
from models_library.rpc.webserver.auth.api_keys import ApiKeyGet
from models_library.users import UserID

from ._api_auth_rpc import get_or_create_api_key_and_secret


def create_unique_api_name_for(product_name: ProductName, user_id: UserID) -> str:
    # NOTE: The namespace chosen doesn't significantly impact the resulting UUID
    # as long as it's consistently used across the same context
    return f"__auto_{uuid5(uuid.NAMESPACE_DNS, f'{product_name}/{user_id}')}"


# NOTE: Uses caching to prevent multiple calls to the external service
# when 'get_or_create_user_api_key' or 'get_or_create_user_api_secret' are invoked.
def _cache_key(fct, *_, **kwargs):
    return f"{fct.__name__}_{kwargs['product_name']}_{kwargs['user_id']}"


@cached(ttl=3, key_builder=_cache_key)
async def _get_or_create_for(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
) -> ApiKeyGet:
    display_name = create_unique_api_name_for(product_name, user_id)
    return await get_or_create_api_key_and_secret(
        app,
        user_id=user_id,
        product_name=product_name,
        display_name=display_name,
        expiration=None,
    )


async def get_or_create_user_api_key(
    app: FastAPI,
    product_name: ProductName,
    user_id: UserID,
) -> str:
    data = await _get_or_create_for(
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
    data = await _get_or_create_for(
        app,
        product_name=product_name,
        user_id=user_id,
    )
    return cast(str, data.api_secret)


__all__: tuple[str, ...] = (
    "get_or_create_user_api_key",
    "get_or_create_user_api_secret",
    "create_unique_api_name_for",
)
