import sqlalchemy as sa
from aiohttp import web
from servicelib.application_keys import APP_DB_ENGINE_KEY

from .db_models import tags
from .login.decorators import RQT_USERID_KEY, login_required


@login_required
async def list_tags(request: web.Request):
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        columns = [col for col in tags.columns if col.key != 'user_id']
        query = sa.select(columns).where(tags.c.user_id == uid)
        result = []
        async for row_proxy in conn.execute(query):
            row_dict = { key: value for key, value in row_proxy.items() }
            result.append(row_dict)
    return result


@login_required
async def update_tag(request: web.Request):
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    tag_id = request.match_info.get('tag_id')
    tag_data = await request.json()
    async with engine.acquire() as conn:
        query = tags.update().values(
            name=tag_data['name'],
            description=tag_data['description'],
            color=tag_data['color']
        ).where(tags.c.id == tag_id).returning(
            tags.c.id,
            tags.c.name,
            tags.c.description,
            tags.c.color
        )
        async with conn.execute(query) as result:
            if result.rowcount == 1:
                row_proxy = await result.first()
                return { key: value for key, value in row_proxy.items() }
            else:
                raise web.HTTPInternalServerError()


@login_required
async def create_tag(request: web.Request):
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    tag_data = await request.json()
    async with engine.acquire() as conn:
        query = tags.insert().values(
            user_id=uid,
            name=tag_data['name'],
            description=tag_data['description'],
            color=tag_data['color']
        ).returning(
            tags.c.id,
            tags.c.name,
            tags.c.description,
            tags.c.color
        )
        async with conn.execute(query) as result:
            if result.rowcount == 1:
                row_proxy = await result.first()
                return { key: value for key, value in row_proxy.items() }
            else:
                raise web.HTTPInternalServerError()


@login_required
async def delete_tag(request: web.Request):
    engine = request.app[APP_DB_ENGINE_KEY]
    tag_id = request.match_info.get('tag_id')
    async with engine.acquire() as conn:
        query = tags.delete().where(tags.c.id == tag_id)
        async with conn.execute(query) as result:
            if result.rowcount == 1:
                raise web.HTTPNoContent(content_type='application/json')
            else:
                raise web.HTTPInternalServerError()
