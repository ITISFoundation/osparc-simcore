import sqlalchemy as sa
from aiohttp import web
from servicelib.application_keys import APP_DB_ENGINE_KEY
from sqlalchemy import and_

from .db_models import tags
from .login.decorators import RQT_USERID_KEY, login_required
from .security_api import check_permission


@login_required
async def list_tags(request: web.Request):
    await check_permission(request, "tag.crud.*")
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        # pylint: disable=not-an-iterable
        columns = [col for col in tags.columns if col.key != "user_id"]
        query = sa.select(columns).where(tags.c.user_id == uid)
        result = []
        async for row_proxy in conn.execute(query):
            row_dict = dict(row_proxy.items())
            result.append(row_dict)
    return result


@login_required
async def update_tag(request: web.Request):
    await check_permission(request, "tag.crud.*")
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    tag_id = request.match_info.get("tag_id")
    tag_data = await request.json()
    async with engine.acquire() as conn:
        # pylint: disable=no-value-for-parameter
        query = (
            tags.update()
            .values(
                name=tag_data["name"],
                description=tag_data["description"],
                color=tag_data["color"],
            )
            .where(and_(tags.c.id == tag_id, tags.c.user_id == uid))
            .returning(tags.c.id, tags.c.name, tags.c.description, tags.c.color)
        )
        async with conn.execute(query) as result:
            if result.rowcount == 1:
                row_proxy = await result.first()
                return dict(row_proxy.items())
            raise web.HTTPInternalServerError()


@login_required
async def create_tag(request: web.Request):
    await check_permission(request, "tag.crud.*")
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    tag_data = await request.json()
    async with engine.acquire() as conn:
        # pylint: disable=no-value-for-parameter
        query = (
            tags.insert()
            .values(
                user_id=uid,
                name=tag_data["name"],
                description=tag_data["description"],
                color=tag_data["color"],
            )
            .returning(tags.c.id, tags.c.name, tags.c.description, tags.c.color)
        )
        async with conn.execute(query) as result:
            if result.rowcount == 1:
                row_proxy = await result.first()
                return dict(row_proxy.items())
            raise web.HTTPInternalServerError()


@login_required
async def delete_tag(request: web.Request):
    await check_permission(request, "tag.crud.*")
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    tag_id = request.match_info.get("tag_id")
    async with engine.acquire() as conn:
        # pylint: disable=no-value-for-parameter
        query = tags.delete().where(and_(tags.c.id == tag_id, tags.c.user_id == uid))
        async with conn.execute(query):
            raise web.HTTPNoContent(content_type="application/json")
