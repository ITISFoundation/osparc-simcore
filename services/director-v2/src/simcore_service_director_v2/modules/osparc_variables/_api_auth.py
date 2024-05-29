import uuid
from typing import Any, cast
from uuid import uuid5

from fastapi import FastAPI
from models_library.api_schemas_webserver.auth import ApiKeyGet
from models_library.products import ProductName
from models_library.users import UserID

from ._api_auth_rpc import get_or_create_api_key_and_secret


def _create_unique_identifier_from(*parts: Any) -> str:
    # NOTE: The namespace chosen doesn't significantly impact the resulting UUID
    # as long as it's consistently used across the same context
    return f"{uuid5(uuid.NAMESPACE_DNS, '/'.join(map(str, parts)) )}"


def create_user_api_name(product_name: ProductName, user_id: UserID) -> str:
    return f"__auto_{_create_unique_identifier_from(product_name, user_id)}"


async def _get_or_create_data(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
) -> ApiKeyGet:

    name = create_user_api_name(product_name, user_id)
    return await get_or_create_api_key_and_secret(
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
