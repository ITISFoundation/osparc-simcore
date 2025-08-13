import logging
from typing import Any, cast

from aiohttp import web
from models_library.conversations import (
    ConversationGetDB,
    ConversationID,
    ConversationPatchDB,
    ConversationType,
)
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import PageTotalCount
from pydantic import NonNegativeInt
from simcore_postgres_database.models.conversations import conversations
from simcore_postgres_database.utils_repos import (
    get_columns_from_db_model,
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy import asc, desc, func
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import select

from ..db.plugin import get_asyncpg_engine
from .errors import ConversationErrorNotFoundError

_logger = logging.getLogger(__name__)


_SELECTION_ARGS = get_columns_from_db_model(conversations, ConversationGetDB)


async def create(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    name: str,
    project_uuid: ProjectID | None,
    user_group_id: GroupID,
    type_: ConversationType,
    product_name: ProductName,
    extra_context: dict[str, Any],
) -> ConversationGetDB:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(
            conversations.insert()
            .values(
                name=name,
                project_uuid=f"{project_uuid}" if project_uuid else None,
                user_group_id=user_group_id,
                type=type_,
                created=func.now(),
                modified=func.now(),
                product_name=product_name,
                extra_context=extra_context,
            )
            .returning(*_SELECTION_ARGS)
        )
        row = result.one()
        return ConversationGetDB.model_validate(row)


async def list_project_conversations(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_uuid: ProjectID,
    # pagination
    offset: NonNegativeInt,
    limit: NonNegativeInt,
    # ordering
    order_by: OrderBy,
) -> tuple[PageTotalCount, list[ConversationGetDB]]:

    base_query = (
        select(*_SELECTION_ARGS)
        .select_from(conversations)
        .where(
            (conversations.c.project_uuid == f"{project_uuid}")
            & (
                conversations.c.type
                in [
                    ConversationType.PROJECT_STATIC,
                    ConversationType.PROJECT_ANNOTATION,
                ]
            )
        )
    )

    # Select total count from base_query
    subquery = base_query.subquery()
    count_query = select(func.count()).select_from(subquery)

    # Ordering and pagination
    if order_by.direction == OrderDirection.ASC:
        list_query = base_query.order_by(
            asc(getattr(conversations.c, order_by.field)),
            conversations.c.conversation_id,
        )
    else:
        list_query = base_query.order_by(
            desc(getattr(conversations.c, order_by.field)),
            conversations.c.conversation_id,
        )
    list_query = list_query.offset(offset).limit(limit)

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        total_count = await conn.scalar(count_query)

        result = await conn.stream(list_query)
        items: list[ConversationGetDB] = [
            ConversationGetDB.model_validate(row) async for row in result
        ]

        return cast(int, total_count), items


async def list_support_conversations_for_user(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_group_id: GroupID,
    # pagination
    offset: NonNegativeInt,
    limit: NonNegativeInt,
    # ordering
    order_by: OrderBy,
) -> tuple[PageTotalCount, list[ConversationGetDB]]:

    base_query = (
        select(*_SELECTION_ARGS)
        .select_from(conversations)
        .where(
            (conversations.c.user_group_id == user_group_id)
            & (conversations.c.type == ConversationType.SUPPORT)
        )
    )

    # Select total count from base_query
    subquery = base_query.subquery()
    count_query = select(func.count()).select_from(subquery)

    # Ordering and pagination
    if order_by.direction == OrderDirection.ASC:
        list_query = base_query.order_by(
            asc(getattr(conversations.c, order_by.field)),
            conversations.c.conversation_id,
        )
    else:
        list_query = base_query.order_by(
            desc(getattr(conversations.c, order_by.field)),
            conversations.c.conversation_id,
        )
    list_query = list_query.offset(offset).limit(limit)

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        total_count = await conn.scalar(count_query)

        result = await conn.stream(list_query)
        items: list[ConversationGetDB] = [
            ConversationGetDB.model_validate(row) async for row in result
        ]

        return cast(int, total_count), items


async def list_all_support_conversations_for_support_user(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    # pagination
    offset: NonNegativeInt,
    limit: NonNegativeInt,
    # ordering
    order_by: OrderBy,
) -> tuple[PageTotalCount, list[ConversationGetDB]]:

    base_query = (
        select(*_SELECTION_ARGS)
        .select_from(conversations)
        .where(conversations.c.type == ConversationType.SUPPORT)
    )

    # Select total count from base_query
    subquery = base_query.subquery()
    count_query = select(func.count()).select_from(subquery)

    # Ordering and pagination
    if order_by.direction == OrderDirection.ASC:
        list_query = base_query.order_by(
            asc(getattr(conversations.c, order_by.field)),
            conversations.c.conversation_id,
        )
    else:
        list_query = base_query.order_by(
            desc(getattr(conversations.c, order_by.field)),
            conversations.c.conversation_id,
        )
    list_query = list_query.offset(offset).limit(limit)

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        total_count = await conn.scalar(count_query)

        result = await conn.stream(list_query)
        items: list[ConversationGetDB] = [
            ConversationGetDB.model_validate(row) async for row in result
        ]

        return cast(int, total_count), items


async def get(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    conversation_id: ConversationID,
) -> ConversationGetDB:
    select_query = (
        select(*_SELECTION_ARGS)
        .select_from(conversations)
        .where(conversations.c.conversation_id == f"{conversation_id}")
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(select_query)
        row = result.one_or_none()
        if row is None:
            raise ConversationErrorNotFoundError(conversation_id=conversation_id)
        return ConversationGetDB.model_validate(row)


async def update(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    conversation_id: ConversationID,
    updates: ConversationPatchDB,
) -> ConversationGetDB:
    # NOTE: at least 'touch' if updated_values is empty
    _updates = {
        **updates.model_dump(exclude_unset=True),
        conversations.c.modified.name: func.now(),
    }

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(
            conversations.update()
            .values(**_updates)
            .where(conversations.c.conversation_id == f"{conversation_id}")
            .returning(*_SELECTION_ARGS)
        )
        row = result.one_or_none()
        if row is None:
            raise ConversationErrorNotFoundError(conversation_id=conversation_id)
        return ConversationGetDB.model_validate(row)


async def delete(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    conversation_id: ConversationID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            conversations.delete().where(
                conversations.c.conversation_id == f"{conversation_id}"
            )
        )
