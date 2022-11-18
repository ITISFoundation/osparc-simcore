from aiohttp import web
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.utils_tags import TagsRepo

from .login.decorators import RQT_USERID_KEY, login_required
from .security_api import check_permission


@login_required
async def list_tags(request: web.Request):
    await check_permission(request, "tag.crud.*")
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]

    repo = TagsRepo(user_id=uid)
    async with engine.acquire() as conn:
        tags = await repo.list_(conn)
        return tags


@login_required
async def update_tag(request: web.Request):
    await check_permission(request, "tag.crud.*")
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    tag_id = request.match_info.get("tag_id")
    tag_data = await request.json()

    repo = TagsRepo(user_id=uid)
    async with engine.acquire() as conn:
        tag = await repo.update(conn, tag_id=tag_id, tag_update=tag_data)
        return tag


@login_required
async def create_tag(request: web.Request):
    await check_permission(request, "tag.crud.*")
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    tag_data = await request.json()

    repo = TagsRepo(user_id=uid)
    async with engine.acquire() as conn:
        tag = await repo.create(conn, tag_create=tag_data)
        return tag


@login_required
async def delete_tag(request: web.Request):
    await check_permission(request, "tag.crud.*")
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    tag_id = request.match_info.get("tag_id")

    repo = TagsRepo(user_id=uid)
    async with engine.acquire() as conn:
        repo.delete(conn, tag_id=tag_id)

    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
