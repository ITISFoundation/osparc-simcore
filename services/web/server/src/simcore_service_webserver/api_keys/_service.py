import datetime as dt
import re
import string
from typing import Final

from aiohttp import web
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.utils_secrets import generate_token_secret_key

from . import _repository
from ._models import ApiKey
from .errors import ApiKeyNotFoundError

_PUNCTUATION_REGEX = re.compile(
    pattern="[" + re.escape(string.punctuation.replace("_", "")) + "]"
)

_KEY_LEN: Final = 10
_SECRET_LEN: Final = 20


def _generate_api_key_and_secret(name: str):
    prefix = _PUNCTUATION_REGEX.sub("_", name[:5])
    api_key = f"{prefix}_{generate_token_secret_key(_KEY_LEN)}"
    api_secret = generate_token_secret_key(_SECRET_LEN)
    return api_key, api_secret


async def create_api_key(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    display_name=str,
    expiration=dt.timedelta,
) -> ApiKey:
    api_key, api_secret = _generate_api_key_and_secret(display_name)

    return await _repository.create_api_key(
        app,
        user_id=user_id,
        product_name=product_name,
        display_name=display_name,
        expiration=expiration,
        api_key=api_key,
        api_secret=api_secret,
    )


async def list_api_keys(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
) -> list[ApiKey]:
    api_keys: list[ApiKey] = await _repository.list_api_keys(
        app, user_id=user_id, product_name=product_name
    )
    return api_keys


async def get_api_key(
    app: web.Application,
    *,
    api_key_id: str,
    user_id: UserID,
    product_name: ProductName,
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


async def get_or_create_api_key(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    display_name: str,
    expiration: dt.timedelta | None = None,
) -> ApiKey:

    key, secret = _generate_api_key_and_secret(display_name)

    api_key: ApiKey = await _repository.get_or_create_api_key(
        app,
        user_id=user_id,
        product_name=product_name,
        display_name=display_name,
        expiration=expiration,
        api_key=key,
        api_secret=secret,
    )

    return api_key


async def delete_api_key(
    app: web.Application,
    *,
    api_key_id: str,
    user_id: UserID,
    product_name: ProductName,
) -> None:
    await _repository.delete_api_key(
        app,
        api_key_id=api_key_id,
        user_id=user_id,
        product_name=product_name,
    )


async def prune_expired_api_keys(app: web.Application) -> list[str]:
    names: list[str] = await _repository.prune_expired(app)
    return names
