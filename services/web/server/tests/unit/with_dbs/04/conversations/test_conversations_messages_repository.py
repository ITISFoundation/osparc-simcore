# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""Contract tests for the conversation-messages repository pagination.

The repository contract: ``total`` is the size of the *match set* (independent of
pagination) and ``items`` is the requested slice, which may legitimately be empty
when ``offset >= total``. Both must be computed from a single statement/snapshot.
"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Final
from uuid import UUID

import pytest
from aiohttp.test_utils import TestClient
from models_library.basic_types import IDStr
from models_library.conversations import ConversationID, ConversationMessageType
from models_library.rest_ordering import OrderBy, OrderDirection
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.conversation_messages import conversation_messages
from simcore_service_webserver.conversations import _conversation_message_repository
from simcore_service_webserver.db.models import UserRole
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


_NUMBER_OF_MESSAGES: Final = 2


async def _create_conversation(client: TestClient, name: str) -> ConversationID:
    assert client.app
    url = client.app.router["list_conversations"].url_for()
    resp = await client.post(f"{url}", json={"name": name, "type": "SUPPORT"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    return UUID(data["conversationId"])


@pytest.fixture
async def conversation_with_two_messages(
    client: TestClient,
    asyncpg_engine: AsyncEngine,
    logged_user: UserInfoDict,
) -> AsyncIterator[ConversationID]:
    conversation_id = await _create_conversation(client, "Repo contract")

    async with AsyncExitStack() as stack:
        for i in range(_NUMBER_OF_MESSAGES):
            await stack.enter_async_context(
                insert_and_get_row_lifespan(
                    asyncpg_engine,
                    table=conversation_messages,
                    values={
                        "conversation_id": conversation_id,
                        "user_group_id": int(logged_user["primary_gid"]),
                        "content": f"message {i + 1}",
                        "type": ConversationMessageType.MESSAGE,
                    },
                    pk_col=conversation_messages.c.message_id,
                )
            )
        yield conversation_id


_ORDER_BY_CREATED_DESC: Final = OrderBy(field=IDStr("created"), direction=OrderDirection.DESC)


async def test_list_messages_total_independent_of_pagination(
    client: TestClient,
    conversation_with_two_messages: ConversationID,
):
    assert client.app

    total, items = await _conversation_message_repository.list_(
        client.app,
        conversation_id=conversation_with_two_messages,
        offset=0,
        limit=20,
        order_by=_ORDER_BY_CREATED_DESC,
    )
    assert total == _NUMBER_OF_MESSAGES
    assert len(items) == _NUMBER_OF_MESSAGES


async def test_list_messages_offset_past_total_returns_empty_page_with_real_total(
    client: TestClient,
    conversation_with_two_messages: ConversationID,
):
    """offset >= total is a valid query: empty page, but total keeps reporting the match set"""
    assert client.app

    total, items = await _conversation_message_repository.list_(
        client.app,
        conversation_id=conversation_with_two_messages,
        offset=100,
        limit=20,
        order_by=_ORDER_BY_CREATED_DESC,
    )
    assert total == _NUMBER_OF_MESSAGES
    assert items == []


async def test_list_messages_empty_conversation(
    client: TestClient,
    logged_user: UserInfoDict,
):
    conversation_id = await _create_conversation(client, "Empty")

    total, items = await _conversation_message_repository.list_(
        client.app,
        conversation_id=conversation_id,
        offset=0,
        limit=20,
        order_by=_ORDER_BY_CREATED_DESC,
    )
    assert total == 0
    assert items == []
