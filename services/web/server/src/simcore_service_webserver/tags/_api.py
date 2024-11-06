""" _api: implements `tags` plugin **service layer**
"""

from aiohttp import web
from models_library.basic_types import IdInt
from models_library.users import UserID
from servicelib.aiohttp.db_asyncpg_engine import get_async_engine
from simcore_postgres_database.utils_tags import TagsRepo
from sqlalchemy.ext.asyncio import AsyncEngine

from .schemas import TagCreate, TagGet, TagUpdate


async def create_tag(
    app: web.Application, user_id: UserID, new_tag: TagCreate
) -> TagGet:
    engine: AsyncEngine = get_async_engine(app)

    repo = TagsRepo(engine)
    tag = await repo.create(
        user_id=user_id,
        read=True,
        write=True,
        delete=True,
        **new_tag.model_dump(exclude_unset=True),
    )
    return TagGet.from_db(tag)


async def list_tags(
    app: web.Application,
    user_id: UserID,
) -> list[TagGet]:
    engine: AsyncEngine = get_async_engine(app)
    repo = TagsRepo(engine)
    tags = await repo.list_all(user_id=user_id)
    return [TagGet.from_db(t) for t in tags]


async def update_tag(
    app: web.Application, user_id: UserID, tag_id: IdInt, tag_updates: TagUpdate
) -> TagGet:
    engine: AsyncEngine = get_async_engine(app)

    repo = TagsRepo(engine)
    tag = await repo.update(
        user_id=user_id,
        tag_id=tag_id,
        **tag_updates.model_dump(exclude_unset=True),
    )
    return TagGet.from_db(tag)


async def delete_tag(app: web.Application, user_id: UserID, tag_id: IdInt):
    engine: AsyncEngine = get_async_engine(app)

    repo = TagsRepo(engine)
    await repo.delete(user_id=user_id, tag_id=tag_id)
