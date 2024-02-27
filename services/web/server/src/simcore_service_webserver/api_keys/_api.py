import re
import string
from typing import Final

from aiohttp import web
from models_library.api_schemas_webserver.auth import ApiKeyCreate, ApiKeyGet
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.utils_secrets import generate_token_secret_key

from ._db import ApiKeyRepo

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
    repo = ApiKeyRepo.create_from_app(app)
    names: list[str] = await repo.list_names(user_id=user_id, product_name=product_name)
    return names


async def create_api_key(
    app: web.Application,
    *,
    new: ApiKeyCreate,
    user_id: UserID,
    product_name: ProductName,
) -> ApiKeyGet:
    prefix = _PUNCTUATION_REGEX.sub("_", new.display_name[:5])
    api_key = f"{prefix}_{generate_token_secret_key(_KEY_LEN)}"
    api_secret = generate_token_secret_key(_SECRET_LEN)

    # raises if name exists already!
    repo = ApiKeyRepo.create_from_app(app)
    await repo.create(
        user_id=user_id,
        product_name=product_name,
        display_name=new.display_name,
        expiration=new.expiration,
        api_key=api_key,
        api_secret=api_secret,
    )

    return ApiKeyGet(
        display_name=new.display_name,
        api_key=api_key,
        api_secret=api_secret,
    )


async def get(
    app: web.Application, *, name: str, user_id: UserID, product_name: ProductName
) -> ApiKeyGet | None:
    repo = ApiKeyRepo.create_from_app(app)
    row = await repo.get(display_name=name, user_id=user_id, product_name=product_name)
    return ApiKeyGet.parse_obj(row) if row else None


async def delete_api_key(
    app: web.Application,
    *,
    name: str,
    user_id: UserID,
    product_name: ProductName,
) -> None:
    repo = ApiKeyRepo.create_from_app(app)
    await repo.delete_by_name(
        display_name=name, user_id=user_id, product_name=product_name
    )


async def prune_expired_api_keys(app: web.Application) -> list[str]:
    repo = ApiKeyRepo.create_from_app(app)
    names: list[str] = await repo.prune_expired()
    return names
