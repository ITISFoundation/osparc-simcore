import logging
from typing import cast

from aiohttp import web
from models_library.conversations import (
    ConversationID,
    ConversationMessageDB,
    ConversationMessageID,
    ConversationMessagePatchDB,
    ConversationMessageType,
)
from models_library.groups import GroupID
from models_library.rest_ordering import OrderBy, OrderDirection
from pydantic import NonNegativeInt
from simcore_postgres_database.models.conversation_messages import conversation_messages
from simcore_postgres_database.utils_repos import (
    get_columns_from_db_model,
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy import asc, desc, func
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import select

from ..db.plugin import get_asyncpg_engine
from .errors import ConversationMessageErrorNotFoundError

_logger = logging.getLogger(__name__)


_SELECTION_ARGS = get_columns_from_db_model(
    conversation_messages, ConversationMessageDB
)


async def create(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    conversation_id: ConversationID,
    user_group_id: GroupID,
    content: str,
    type_: ConversationMessageType,
) -> ConversationMessageDB:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(
            conversation_messages.insert()
            .values(
                conversation_id=conversation_id,
                user_group_id=user_group_id,
                content=content,
                type=type_,
                created=func.now(),
                modified=func.now(),
            )
            .returning(*_SELECTION_ARGS)
        )
        row = result.one()
        return ConversationMessageDB.model_validate(row)


async def list_(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    conversation_id: ConversationID,
    # pagination
    offset: NonNegativeInt,
    limit: NonNegativeInt,
    # ordering
    order_by: OrderBy,
) -> tuple[int, list[ConversationMessageDB]]:

    base_query = (
        select(*_SELECTION_ARGS)
        .select_from(conversation_messages)
        .where(conversation_messages.c.conversation_id == conversation_id)
    )

    # Select total count from base_query
    subquery = base_query.subquery()
    count_query = select(func.count()).select_from(subquery)

    # Ordering and pagination
    if order_by.direction == OrderDirection.ASC:
        list_query = base_query.order_by(
            asc(getattr(conversation_messages.c, order_by.field)),
            conversation_messages.c.message_id,
        )
    else:
        list_query = base_query.order_by(
            desc(getattr(conversation_messages.c, order_by.field)),
            conversation_messages.c.message_id,
        )
    list_query = list_query.offset(offset).limit(limit)

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        total_count = await conn.scalar(count_query)

        result = await conn.stream(list_query)
        items: list[ConversationMessageDB] = [
            ConversationMessageDB.model_validate(row) async for row in result
        ]

        return cast(int, total_count), items


async def get(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
) -> ConversationMessageDB:
    select_query = (
        select(*_SELECTION_ARGS)
        .select_from(conversation_messages)
        .where(
            (conversation_messages.c.conversation_id == conversation_id)
            & (conversation_messages.c.message_id == message_id)
        )
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(select_query)
        row = result.one_or_none()
        if row is None:
            raise ConversationMessageErrorNotFoundError(
                conversation_id=conversation_id, message_id=message_id
            )
        return ConversationMessageDB.model_validate(row)


async def update(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
    updates: ConversationMessagePatchDB,
) -> ConversationMessageDB:
    # NOTE: at least 'touch' if updated_values is empty
    _updates = {
        **updates.model_dump(exclude_unset=True),
        conversation_messages.c.modified.name: func.now(),
    }

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(
            conversation_messages.update()
            .values(**_updates)
            .where(
                (conversation_messages.c.conversation_id == conversation_id)
                & (conversation_messages.c.message_id == message_id)
            )
            .returning(*_SELECTION_ARGS)
        )
        row = result.one_or_none()
        if row is None:
            raise ConversationMessageErrorNotFoundError(
                conversation_id=conversation_id, message_id=message_id
            )
        return ConversationMessageDB.model_validate(row)


async def delete(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            conversation_messages.delete().where(
                (conversation_messages.c.conversation_id == conversation_id)
                & (conversation_messages.c.message_id == message_id)
            )
        )
