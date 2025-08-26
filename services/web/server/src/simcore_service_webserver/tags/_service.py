"""Implements `tags` plugin **service layer**"""

from aiohttp import web
from common_library.groups_dicts import AccessRightsDict
from common_library.users_enums import UserRole
from models_library.basic_types import IdInt
from models_library.groups import EVERYONE_GROUP_ID, GroupID
from models_library.users import UserID
from servicelib.aiohttp.db_asyncpg_engine import get_async_engine
from simcore_postgres_database.utils_tags import TagAccessRightsDict, TagsRepo
from sqlalchemy.ext.asyncio import AsyncEngine

from ..products import products_service
from ..users import users_service
from .errors import (
    InsufficientTagShareAccessError,
    ShareTagWithEveryoneNotAllowedError,
    ShareTagWithProductGroupNotAllowedError,
)
from .schemas import TagCreate, TagGet, TagUpdate


async def create_tag(
    app: web.Application, user_id: UserID, new_tag: TagCreate
) -> TagGet:
    """Creates tag and user_id takes ownership"""
    engine: AsyncEngine = get_async_engine(app)

    repo = TagsRepo(engine)
    tag = await repo.create(
        user_id=user_id,
        read=True,
        write=True,
        delete=True,
        **new_tag.model_dump(exclude_unset=True),
    )
    return TagGet.from_domain_model(tag)


async def list_tags(
    app: web.Application,
    user_id: UserID,
) -> list[TagGet]:
    engine: AsyncEngine = get_async_engine(app)
    repo = TagsRepo(engine)
    tags = await repo.list_all(user_id=user_id)
    return [TagGet.from_domain_model(t) for t in tags]


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
    return TagGet.from_domain_model(tag)


async def delete_tag(app: web.Application, user_id: UserID, tag_id: IdInt):
    engine: AsyncEngine = get_async_engine(app)

    repo = TagsRepo(engine)
    await repo.delete(user_id=user_id, tag_id=tag_id)


def _is_product_group(app: web.Application, group_id: GroupID):
    products = products_service.list_products(app)
    return any(group_id == p.group_id for p in products)


async def _validate_tag_sharing_permissions(
    app: web.Application,
    repo: TagsRepo,
    *,
    caller_user_id: UserID,
    tag_id: IdInt,
    group_id: GroupID,
) -> None:
    """
    Raises:
        ShareTagWithEveryoneNotAllowedError
        ShareTagWithProductGroupNotAllowedError
        InsufficientWriteAccessTagError
    """
    if group_id == EVERYONE_GROUP_ID:
        raise ShareTagWithEveryoneNotAllowedError(
            user_id=caller_user_id, tag_id=tag_id, group_id=group_id
        )

    if _is_product_group(app, group_id=group_id):
        user_role: UserRole = await users_service.get_user_role(
            app, user_id=caller_user_id
        )
        if user_role < UserRole.TESTER:
            raise ShareTagWithProductGroupNotAllowedError(
                user_id=caller_user_id,
                tag_id=tag_id,
                group_id=group_id,
                user_role=user_role,
            )

    if not await repo.has_access_rights(
        user_id=caller_user_id, tag_id=tag_id, write=True
    ):
        raise InsufficientTagShareAccessError(
            user_id=caller_user_id, tag_id=tag_id, group_id=group_id
        )


async def share_tag_with_group(
    app: web.Application,
    *,
    caller_user_id: UserID,
    tag_id: IdInt,
    group_id: GroupID,
    access_rights: AccessRightsDict,
) -> TagAccessRightsDict:
    """
    Raises:
        ShareTagWithEveryoneNotAllowedError
        ShareTagWithProductGroupNotAllowedError
        InsufficientWriteAccessTagError
        TagOperationNotAllowedError
        TagsValueError
    """
    repo = TagsRepo(get_async_engine(app))

    await _validate_tag_sharing_permissions(
        app, repo, caller_user_id=caller_user_id, tag_id=tag_id, group_id=group_id
    )

    return await repo.create_or_update_access_rights(
        tag_id=tag_id,
        group_id=group_id,
        **access_rights,
    )


async def unshare_tag_with_group(
    app: web.Application,
    *,
    caller_user_id: UserID,
    tag_id: IdInt,
    group_id: GroupID,
) -> bool:
    """
    Raises:
        TagOperationNotAllowedError

    Returns:
        True if unshared (NOTE: will not raise if not found)
    """
    repo = TagsRepo(get_async_engine(app))

    await _validate_tag_sharing_permissions(
        app, repo, caller_user_id=caller_user_id, tag_id=tag_id, group_id=group_id
    )

    deleted: bool = await repo.delete_access_rights(tag_id=tag_id, group_id=group_id)
    return deleted


async def list_tag_groups(
    app: web.Application,
    *,
    caller_user_id: UserID,
    tag_id: IdInt,
) -> list[TagAccessRightsDict]:
    """Returns list of groups sharing this tag"""
    repo = TagsRepo(get_async_engine(app))

    if not await repo.has_access_rights(
        user_id=caller_user_id, tag_id=tag_id, read=True
    ):
        return []

    return await repo.list_access_rights(tag_id=tag_id)
