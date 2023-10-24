import logging
from typing import Final

from aiohttp import web
from models_library.api_schemas_webserver.auth import ApiKeyCreate, ApiKeyGet
from models_library.users import UserID

from ._api_keys_db import ApiKeyRepo
from .utils import get_random_string

_logger = logging.getLogger(__name__)

_KEY_LEN: Final = 10
_SECRET_LEN: Final = 30


async def list_api_keys(app: web.Application, *, user_id: UserID) -> list[str]:
    repo = ApiKeyRepo.create_from_app(app, user_id=user_id)
    return await repo.list_names()


async def create_api_key(
    app: web.Application, *, new: ApiKeyCreate, user_id: UserID
) -> ApiKeyGet:

    api_key = get_random_string(_KEY_LEN)
    api_secret = get_random_string(_SECRET_LEN)

    # raises if name exists already!
    repo = ApiKeyRepo.create_from_app(app, user_id=user_id)
    await repo.create(
        new,
        api_key=api_key,
        api_secret=api_secret,
    )

    return ApiKeyGet(
        display_name=new.display_name,
        api_key=api_key,
        api_secret=api_secret,
    )


async def delete_api_key(app: web.Application, *, name: str, user_id: UserID) -> None:
    repo = ApiKeyRepo.create_from_app(app, user_id=user_id)
    await repo.delete(name)


async def prune_expired_api_keys(app: web.Application) -> list[str]:
    repo = ApiKeyRepo.create_from_app(app)
    return await repo.prune_expired()
