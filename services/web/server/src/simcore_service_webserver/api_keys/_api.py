import re
import string
from datetime import timedelta
from typing import Final

from aiohttp import web
from models_library.api_schemas_webserver.auth import ApiKeyCreate, ApiKeyGet
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.utils_secrets import generate_token_secret_key

from . import _db as db

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
    names: list[str] = await db.list_names(
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
    new: ApiKeyCreate,
    user_id: UserID,
    product_name: ProductName,
) -> ApiKeyGet:
    # generate key and secret
    api_key, api_secret = _generate_api_key_and_secret(new.display_name)

    # raises if name exists already!
    api_key_id = await db.create(
        app,
        user_id=user_id,
        product_name=product_name,
        display_name=new.display_name,
        expiration=new.expiration,
        api_key=api_key,
        api_secret=api_secret,
    )

    return ApiKeyGet(
        id_=api_key_id,
        display_name=new.display_name,
        api_key=api_key,
        api_secret=api_secret,
    )


async def get_api_key(
    app: web.Application, *, name: str, user_id: UserID, product_name: ProductName
) -> ApiKeyGet | None:
    row = await db.get(
        app, display_name=name, user_id=user_id, product_name=product_name
    )
    return ApiKeyGet.model_validate(row) if row else None


async def get_or_create_api_key(
    app: web.Application,
    *,
    name: str,
    user_id: UserID,
    product_name: ProductName,
    expiration: timedelta | None = None,
) -> ApiKeyGet:

    api_key, api_secret = _generate_api_key_and_secret(name)

    row = await db.get_or_create(
        app,
        user_id=user_id,
        product_name=product_name,
        display_name=name,
        expiration=expiration,
        api_key=api_key,
        api_secret=api_secret,
    )
    return ApiKeyGet.model_construct(
        display_name=row.display_name, api_key=row.api_key, api_secret=row.api_secret
    )


async def delete_api_key(
    app: web.Application,
    *,
    api_key_id: int,
    user_id: UserID,
    product_name: ProductName,
) -> None:
    await db.delete(
        app, api_key_id=api_key_id, user_id=user_id, product_name=product_name
    )


async def prune_expired_api_keys(app: web.Application) -> list[str]:
    names: list[str] = await db.prune_expired(app)
    return names
