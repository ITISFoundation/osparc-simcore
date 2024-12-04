import datetime as dt
import re
import string
from typing import Final

from aiohttp import web
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.utils_secrets import generate_token_secret_key
from simcore_service_webserver.api_keys._models import ApiKey

from . import _db
from .errors import ApiKeyNotFoundError

_PUNCTUATION_REGEX = re.compile(
    pattern="[" + re.escape(string.punctuation.replace("_", "")) + "]"
)

_KEY_LEN: Final = 10
_SECRET_LEN: Final = 20


async def list_api_keys(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
) -> list[str]:
    names: list[str] = await _db.list_display_names(
        app, user_id=user_id, product_name=product_name
    )
    return names


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
    # generate key and secret
    api_key, api_secret = _generate_api_key_and_secret(display_name)

    return await _db.create(
        app,
        user_id=user_id,
        product_name=product_name,
        display_name=display_name,
        expiration=expiration,
        api_key=api_key,
        api_secret=api_secret,
    )


async def get_api_key(
    app: web.Application,
    *,
    api_key_id: int,
    user_id: UserID,
    product_name: ProductName,
) -> ApiKey:
    api_key = await _db.get(
        app, api_key_id=api_key_id, user_id=user_id, product_name=product_name
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

    api_key, api_secret = _generate_api_key_and_secret(display_name)

    return await _db.get_or_create(
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
    api_key_id: int,
    user_id: UserID,
    product_name: ProductName,
) -> None:
    await _db.delete(
        app,
        api_key_id=api_key_id,
        user_id=user_id,
        product_name=product_name,
    )


async def prune_expired_api_keys(app: web.Application) -> list[str]:
    names: list[str] = await _db.prune_expired(app)
    return names
