import sqlalchemy as sa
from aiohttp import web
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from sqlalchemy import and_

from .db_models import folders
from .login.decorators import RQT_USERID_KEY, login_required
from .security_api import check_permission


@login_required
async def list_folders(request: web.Request):
    await check_permission(request, "folder.crud.*")
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        # pylint: disable=not-an-iterable
        columns = [col for col in folders.columns if col.key != "user_id"]
        query = sa.select(columns).where(folders.c.user_id == uid)
        result = []
        async for row_proxy in conn.execute(query):
            row_dict = dict(row_proxy.items())
            result.append(row_dict)
    return result


@login_required
async def update_folder(request: web.Request):
    await check_permission(request, "folder.crud.*")
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    folder_id = request.match_info.get("folder_id")
    folder_data = await request.json()
    async with engine.acquire() as conn:
        # pylint: disable=no-value-for-parameter
        query = (
            folders.update()
            .values(
                name=folder_data["name"],
                description=folder_data["description"],
                color=folder_data["color"],
            )
            .where(and_(folders.c.id == folder_id, folders.c.user_id == uid))
            .returning(
                folders.c.id, folders.c.name, folders.c.description, folders.c.color
            )
        )
        async with conn.execute(query) as result:
            if result.rowcount == 1:
                row_proxy = await result.first()
                return dict(row_proxy.items())
            raise web.HTTPInternalServerError()


@login_required
async def create_folder(request: web.Request):
    await check_permission(request, "folder.crud.*")
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    folder_data = await request.json()
    async with engine.acquire() as conn:
        # pylint: disable=no-value-for-parameter
        query = (
            folders.insert()
            .values(
                user_id=uid,
                name=folder_data["name"],
                description=folder_data["description"],
                color=folder_data["color"],
            )
            .returning(
                folders.c.id, folders.c.name, folders.c.description, folders.c.color
            )
        )
        async with conn.execute(query) as result:
            if result.rowcount == 1:
                row_proxy = await result.first()
                return dict(row_proxy.items())
            raise web.HTTPInternalServerError()


@login_required
async def delete_folder(request: web.Request):
    await check_permission(request, "folder.crud.*")
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    folder_id = request.match_info.get("folder_id")
    async with engine.acquire() as conn:
        # pylint: disable=no-value-for-parameter
        query = folders.delete().where(
            and_(folders.c.id == folder_id, folders.c.user_id == uid)
        )
        async with conn.execute(query):
            raise web.HTTPNoContent(content_type="application/json")
