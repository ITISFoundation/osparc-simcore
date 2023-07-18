import logging
import uuid as uuidlib
from datetime import timedelta
from typing import Any, ClassVar, TypedDict

import simcore_postgres_database.webserver_models as orm
import sqlalchemy as sa
from aiohttp import web
from aiohttp.web import RouteTableDef
from aiopg.sa.result import ResultProxy
from models_library.basic_types import IdInt
from pydantic import BaseModel, Field
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from servicelib.aiohttp.requests_validation import parse_request_body_as
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from simcore_postgres_database.errors import DatabaseError
from sqlalchemy.sql import func

from ..security.api import check_permission
from .decorators import login_required
from .utils import get_random_string

log = logging.getLogger(__name__)


#
# MODELS
#


class ApiKeyCreate(BaseModel):
    display_name: str = Field(..., min_length=3)
    expiration: timedelta | None = Field(
        None,
        description="Time delta from creation time to expiration. If None, then it does not expire.",
    )

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "display_name": "test-api-forever",
                },
                {
                    "display_name": "test-api-for-one-day",
                    "expiration": 60 * 60 * 24,
                },
            ]
        }


class ApiKeyGet(BaseModel):
    display_name: str = Field(..., min_length=3)
    api_key: str
    api_secret: str

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {"display_name": "myapi", "api_key": "key", "api_secret": "secret"},
            ]
        }


#
# HANDLERS / helpers
#


class ApiCredentials(TypedDict):
    api_key: str
    api_secret: str


def _get_random_uuid_string() -> str:
    return uuidlib.uuid5(uuidlib.NAMESPACE_DNS, get_random_string(20)).hex


def generate_api_credentials() -> ApiCredentials:
    return ApiCredentials(
        api_key=_get_random_uuid_string(), api_secret=_get_random_uuid_string()
    )


class ApiKeyRepo:
    # pylint: disable=no-value-for-parameter

    def __init__(self, request: web.Request):
        self.engine = request.app[APP_DB_ENGINE_KEY]
        self.user_id: int = request.get(RQT_USERID_KEY, -1)

    async def list_names(self):
        async with self.engine.acquire() as conn:
            stmt = sa.select(
                [
                    orm.api_keys.c.display_name,
                ]
            ).where(orm.api_keys.c.user_id == self.user_id)

            result: ResultProxy = await conn.execute(stmt)
            return [r.display_name for r in await result.fetchall()]

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
            return [r.id for r in await result.fetchall()]

    async def delete(self, name: str):
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


routes = RouteTableDef()


@routes.get("/v0/auth/api-keys", name="list_api_keys")
@login_required
async def list_api_keys(request: web.Request):
    await check_permission(request, "user.apikey.*")

    crud = ApiKeyRepo(request)
    return await crud.list_names()


@routes.post("/v0/auth/api-keys", name="create_api_key")
@login_required
async def create_api_key(request: web.Request):
    await check_permission(request, "user.apikey.*")

    api_key = await parse_request_body_as(ApiKeyCreate, request)
    credentials = generate_api_credentials()
    try:
        repo = ApiKeyRepo(request)
        await repo.create(api_key, **credentials)
    except DatabaseError as err:
        raise web.HTTPBadRequest(
            reason="Invalid API key name: already exists",
            content_type=MIMETYPE_APPLICATION_JSON,
        ) from err

    return ApiKeyGet(
        display_name=api_key.display_name,
        api_key=credentials["api_key"],
        api_secret=credentials["api_secret"],
    ).dict(**RESPONSE_MODEL_POLICY)


@routes.delete("/v0/auth/api-keys", name="delete_api_key")
@login_required
async def delete_api_key(request: web.Request):
    await check_permission(request, "user.apikey.*")

    body = await request.json()
    display_name = body.get("display_name")

    try:
        repo = ApiKeyRepo(request)
        await repo.delete(display_name)
    except DatabaseError as err:
        log.warning(
            "Failed to delete API key %s. Ignoring error", display_name, exc_info=err
        )

    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
