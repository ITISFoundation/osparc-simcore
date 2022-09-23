import logging
import uuid as uuidlib
from copy import deepcopy
from datetime import timedelta
from typing import Optional

import simcore_postgres_database.webserver_models as orm
import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.result import ResultProxy
from models_library.basic_types import IdInt
from pydantic import BaseModel
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from servicelib.aiohttp.requests_validation import parse_request_body_as
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.errors import DatabaseError
from sqlalchemy.sql import func

from ..security_api import check_permission
from .decorators import RQT_USERID_KEY, login_required
from .utils import get_random_string

log = logging.getLogger(__name__)


#
# MODELS
#


class ApiKeyCreate(BaseModel):
    # TODO: bigger than 3 letters
    display_name: str
    expiration: Optional[timedelta] = None
    # TODO: add update OAS!!


# TODO: class ApiKeyGet(BaseModel): for the response


#
# HANDLERS / helpers
#


def generate_api_credentials() -> dict[str, str]:
    credentials: dict = dict.fromkeys(("api_key", "api_secret"), "")
    for name in deepcopy(credentials):
        value = get_random_string(20)
        credentials[name] = str(uuidlib.uuid5(uuidlib.NAMESPACE_DNS, value))
    return credentials


class CRUD:
    # pylint: disable=no-value-for-parameter

    def __init__(self, request: web.Request):
        self.engine = request.app[APP_DB_ENGINE_KEY]
        self.user_id: int = request.get(RQT_USERID_KEY, -1)

    async def list_api_key_names(self):
        async with self.engine.acquire() as conn:
            stmt = sa.select(
                [
                    orm.api_keys.c.display_name,
                ]
            ).where(orm.api_keys.c.user_id == self.user_id)

            result: ResultProxy = await conn.execute(stmt)
            listed = [r.display_name for r in result.fetchall()]
            return listed

    async def create(
        self,
        request_data: ApiKeyCreate,
        *,
        api_key: str,
        api_secret: str,
    ) -> list[IdInt]:
        async with self.engine.acquire() as conn:
            stmt = (
                orm.api_keys.insert()
                .values(
                    display_name=request_data.display_name,
                    user_id=self.user_id,
                    api_key=api_key,
                    api_secret=api_secret,
                    expires_at=func.now() + request_data.expiration
                    if request_data.expiration
                    else None,
                )
                .returning(orm.api_keys.c.id)
            )

            result: ResultProxy = await conn.execute(stmt)
            created = [r.id for r in await result.fetchall()]
            return created

    async def delete_api_key(self, name: str):
        async with self.engine.acquire() as conn:
            stmt = orm.api_keys.delete().where(
                sa.and_(
                    orm.api_keys.c.user_id == self.user_id,
                    orm.api_keys.c.display_name == name,
                )
            )
            await conn.execute(stmt)


#
# HANDLERS
#


@login_required
async def list_api_keys(request: web.Request):
    """
    GET /auth/api-keys
    """
    await check_permission(request, "user.apikey.*")

    crud = CRUD(request)
    names = await crud.list_api_key_names()
    return names


@login_required
async def create_api_key(request: web.Request):
    """
    POST /auth/api-keys
    """
    await check_permission(request, "user.apikey.*")

    api_key = await parse_request_body_as(ApiKeyCreate, request)
    credentials = generate_api_credentials()
    try:
        crud = CRUD(request)
        await crud.create(api_key, **credentials)
    except DatabaseError as err:
        raise web.HTTPBadRequest(
            reason="Invalid API key name: already exists",
            content_type=MIMETYPE_APPLICATION_JSON,
        ) from err

    return {
        "display_name": api_key.display_name,
        "api_key": credentials["api_key"],
        "api_secret": credentials["api_secret"],
    }


@login_required
async def delete_api_key(request: web.Request):
    """
    DELETE /auth/api-keys
    """
    await check_permission(request, "user.apikey.*")

    body = await request.json()
    display_name = body.get("display_name")

    try:
        crud = CRUD(request)
        await crud.delete_api_key(display_name)
    except DatabaseError as err:
        log.warning(
            "Failed to delete API key %s. Ignoring error", display_name, exc_info=err
        )

    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
