""" _api: implements `tags` plugin **service layer**
"""

from aiohttp import web
from models_library.basic_types import IdInt
from models_library.projects import ProjectID
from models_library.rabbitmq_messages import RabbitResourceTrackingProjectSyncMessage
from models_library.users import UserID
from servicelib.aiohttp.db_asyncpg_engine import get_async_engine
from simcore_postgres_database.utils_tags import TagsRepo
from sqlalchemy.ext.asyncio import AsyncEngine

from .schemas import TagCreate, TagGet, TagUpdate


async def inform_rut_about_tag_change(tags_repo: TagsRepo, rabbit_client, project_id: ProjectID | None, ):
    # Inform RUT about tag change


    if project_id:
        project_tags = await tags_repo.list_tag_ids_and_names_by_project_uuid(
            project_uuid=project_id
        )


    await rabbit_client.publish(
        RabbitResourceTrackingProjectSyncMessage.channel_name,
        RabbitResourceTrackingProjectSyncMessage(
            project_tags=project_tags
        ),
    )


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
        **new_tag.dict(exclude_unset=True),
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
    _tags_updates_exclude_unset = tag_updates.dict(exclude_unset=True)
    tag = await repo.update(
        user_id=user_id,
        tag_id=tag_id,
        **_tags_updates_exclude_unset,
    )

    # If tag_updates name
    if _tags_updates_exclude_unset.get("name") is not None:
        await inform_rut_about_tag_change(tags_repo=repo, rabbit_client=)

    return TagGet.from_db(tag)


async def delete_tag(app: web.Application, user_id: UserID, tag_id: IdInt):
    engine: AsyncEngine = get_async_engine(app)

    repo = TagsRepo(engine)

    # Sync with RUT
    # NOTE: Careful this will delete all the tags also historitically in the RUT

    await repo.delete(user_id=user_id, tag_id=tag_id)
