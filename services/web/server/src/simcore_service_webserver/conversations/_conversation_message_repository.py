import logging

import sqlalchemy as sa
from aiohttp import web
from models_library.conversations import (
    ConversationID,
    ConversationMessageGetDB,
    ConversationMessageID,
    ConversationMessagePatchDB,
    ConversationMessageType,
)
from models_library.groups import GroupID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import PageTotalCount
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
from .errors import (
    ConversationErrorNotFoundError,
    ConversationMessageErrorNotFoundError,
)

_logger = logging.getLogger(__name__)


_SELECTION_ARGS = get_columns_from_db_model(conversation_messages, ConversationMessageGetDB)


async def create(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    conversation_id: ConversationID,
    user_group_id: GroupID,
    content: str,
    type_: ConversationMessageType,
) -> ConversationMessageGetDB:
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
        row = result.mappings().one_or_none()
        if row is None:
            raise ConversationErrorNotFoundError(conversation_id=conversation_id)

        return ConversationMessageGetDB.model_validate(row)


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
) -> tuple[PageTotalCount, list[ConversationMessageGetDB]]:
    # NOTE: total and page are computed in a SINGLE statement so they share one snapshot.
    # Two separate statements would each take their own snapshot (READ COMMITTED), and a
    # concurrent commit in between could make the page show rows the count never saw
    # (i.e. count > total).
    #
    # The statement is driven FROM the single-row total CTE and LEFT JOINs the paged rows,
    # so the total is also emitted when the page is empty (e.g. offset >= total), keeping
    # `total` a property of the match set and independent of pagination.
    total_cte = (
        select(func.count().label("_total_count"))
        .where(conversation_messages.c.conversation_id == conversation_id)
        .cte("total_count")
    )

    # Ordering and pagination of the page rows
    page_query = select(*_SELECTION_ARGS).where(conversation_messages.c.conversation_id == conversation_id)
    if order_by.direction == OrderDirection.ASC:
        page_query = page_query.order_by(
            asc(getattr(conversation_messages.c, order_by.field)),
            conversation_messages.c.message_id,
        )
    else:
        page_query = page_query.order_by(
            desc(getattr(conversation_messages.c, order_by.field)),
            conversation_messages.c.message_id,
        )
    page_subquery = page_query.offset(offset).limit(limit).subquery("page")

    list_query = (
        select(
            total_cte.c._total_count,  # noqa: SLF001
            *(page_subquery.c[column.name] for column in _SELECTION_ARGS),
        )
        .select_from(total_cte)
        .outerjoin(page_subquery, sa.true())
    )

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(list_query)

        items: list[ConversationMessageGetDB] = []
        total_count: int = 0
        for row_mapping in result.mappings():
            row_dict = dict(row_mapping)
            total_count = row_dict.pop("_total_count")
            if row_dict["message_id"] is not None:  # empty page: page columns are NULL
                items.append(ConversationMessageGetDB.model_validate(row_dict))

        return total_count, items


async def get(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
) -> ConversationMessageGetDB:
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
            raise ConversationMessageErrorNotFoundError(conversation_id=conversation_id, message_id=message_id)
        return ConversationMessageGetDB.model_validate(row)


async def update(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    conversation_id: ConversationID,
    message_id: ConversationMessageID,
    updates: ConversationMessagePatchDB,
) -> ConversationMessageGetDB:
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
            raise ConversationMessageErrorNotFoundError(conversation_id=conversation_id, message_id=message_id)
        return ConversationMessageGetDB.model_validate(row)


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
