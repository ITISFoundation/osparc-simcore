import logging
import uuid as uuidlib
from typing import Dict, List

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.result import ResultProxy, RowProxy

import simcore_postgres_database.webserver_models as orm
from servicelib.aiopg_utils import DatabaseError
from servicelib.application_keys import APP_DB_ENGINE_KEY

from ..security_api import check_permission
from .decorators import RQT_USERID_KEY, login_required
from .utils import get_random_string

log = logging.getLogger(__name__)


def generate_api_credentials() -> Dict[str, str]:
    credentials: Dict = dict.fromkeys(("api_key", "api_secret"), "")
    for name in credentials:
        value = get_random_string(20)
        credentials[name] = str(uuidlib.uuid5(uuidlib.NAMESPACE_DNS, value))
    return credentials


class CRUD:
    # pylint: disable=no-value-for-parameter

    def __init__(self, request: web.Request):
        self.engine = request.app.get(APP_DB_ENGINE_KEY)
        self.userid: int = request.get(RQT_USERID_KEY, -1)

    async def list_api_key_names(self):
        async with self.engine.acquire() as conn:
            stmt = sa.select([orm.api_keys.c.display_name,]).where(
                orm.api_keys.c.user_id == self.userid
            )

            res: ResultProxy = await conn.execute(stmt)
            rows: List[RowProxy] = await res.fetchall()
            return [row.get(0) for row in rows] if rows else []

    async def create(self, name: str, *, api_key: str, api_secret: str):

        async with self.engine.acquire() as conn:
            stmt = orm.api_keys.insert().values(
                display_name=name,
                user_id=self.userid,
                api_key=api_key,
                api_secret=api_secret,
            )

            res: ResultProxy = await conn.execute(stmt)
            print(res)

    async def delete_api_key(self, name: str):
        async with self.engine.acquire() as conn:
            stmt = orm.api_keys.delete().where(
                sa.and_(
                    orm.api_keys.c.user_id == self.userid,
                    orm.api_keys.c.display_name == name,
                )
            )
            await conn.execute(stmt)


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

    body = await request.json()
    display_name = body.get("display_name")

    credentials = generate_api_credentials()
    try:
        crud = CRUD(request)
        await crud.create(display_name, **credentials)
    except DatabaseError as err:
        log.warning("Failed to create API key %d", display_name, exc_info=err)
        raise web.HTTPBadRequest(reason="Invalid API key name: already exists") from err

    return {
        "display_name": display_name,
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
            "Failed to delete API key %d. Ignoring error", display_name, exc_info=err
        )

    raise web.HTTPNoContent
