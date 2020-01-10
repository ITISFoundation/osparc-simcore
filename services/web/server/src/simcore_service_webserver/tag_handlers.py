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
        query = sa.select(columns).where(tags.c.owner == uid)
        result = await conn.execute(query)
    return result.fetchall()


@login_required
async def update_tag(request: web.Request):
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    return await request.json()


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
        )
        result = await conn.execute(query)
    return await request.json()


@login_required
async def delete_tag(request: web.Request):
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    raise web.HTTPNoContent(content_type='application/json')
