import datetime as dt

from aiohttp import web
from models_library.products import ProductName
from models_library.rpc.webserver.auth.api_keys import (
    generate_api_key_and_secret,
)
from models_library.users import UserID

from . import _repository
from .errors import ApiKeyNotFoundError
from .models import ApiKey


async def create_api_key(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    display_name: str,
    expiration: dt.timedelta | None,
) -> ApiKey:
    api_key, api_secret = generate_api_key_and_secret(display_name)

    return await _repository.create_api_key(
        app,
        user_id=user_id,
        product_name=product_name,
        display_name=display_name,
        expiration=expiration,
        api_key=api_key,
        api_secret=api_secret,
    )


async def delete_api_key(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    api_key_id: str,
) -> None:
    await _repository.delete_api_key(
        app,
        api_key_id=api_key_id,
        user_id=user_id,
        product_name=product_name,
    )


async def delete_api_key_by_key(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    api_key: str,
) -> None:
    await _repository.delete_api_key_by_key(
        app,
        product_name=product_name,
        user_id=user_id,
        api_key=api_key,
    )


async def get_api_key(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    api_key_id: str,
) -> ApiKey:
    api_key: ApiKey | None = await _repository.get_api_key(
        app,
        api_key_id=api_key_id,
        user_id=user_id,
        product_name=product_name,
    )
    if api_key is not None:
        return api_key

    raise ApiKeyNotFoundError(api_key_id=api_key_id)


async def list_api_keys(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
) -> list[ApiKey]:
    api_keys: list[ApiKey] = await _repository.list_api_keys(
        app, user_id=user_id, product_name=product_name
    )
    return api_keys


async def prune_expired_api_keys(app: web.Application) -> list[str]:
    names: list[str] = await _repository.delete_expired_api_keys(app)
    return names
