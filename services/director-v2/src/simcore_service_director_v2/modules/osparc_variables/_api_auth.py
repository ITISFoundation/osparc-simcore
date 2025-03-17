from datetime import timedelta
from uuid import uuid4

from aiocache import cached  # type: ignore[import-untyped]
from fastapi import FastAPI
from models_library.products import ProductName
from models_library.rpc.webserver.auth.api_keys import ApiKeyGet
from models_library.users import UserID

from ._api_auth_rpc import create_api_key as rpc_create_api_key

_EXPIRATION_AUTO_KEYS = timedelta(weeks=4)


# NOTE: Uses caching to prevent multiple calls to the external service
# when 'get_or_create_user_api_key' or 'get_or_create_user_api_secret' are invoked.
def _cache_key(fct, *_, **kwargs):
    return f"{fct.__name__}_{kwargs['product_name']}_{kwargs['user_id']}"


@cached(ttl=3, key_builder=_cache_key)
async def _create_for(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
) -> ApiKeyGet:
    return await rpc_create_api_key(
        app,
        user_id=user_id,
        product_name=product_name,
        display_name=f"__auto_{uuid4()}",
        expiration=_EXPIRATION_AUTO_KEYS,
    )


async def create_user_api_key(
    app: FastAPI,
    product_name: ProductName,
    user_id: UserID,
) -> str:
    data = await _create_for(
        app,
        product_name=product_name,
        user_id=user_id,
    )
    assert data.api_key  # nosec
    return data.api_key


async def create_user_api_secret(
    app: FastAPI,
    product_name: ProductName,
    user_id: UserID,
) -> str:
    data = await _create_for(
        app,
        product_name=product_name,
        user_id=user_id,
    )
    assert data.api_secret  # nosec
    return data.api_secret


__all__: tuple[str, ...] = (
    "create_user_api_key",
    "create_user_api_secret",
)
