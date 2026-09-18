# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""Contract tests for the conversation-messages repository pagination.

The repository contract: ``total`` is the size of the *match set* (independent of
pagination) and ``items`` is the requested slice, which may legitimately be empty
when ``offset >= total``. Both must be computed from a single statement/snapshot.
"""

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from models_library.basic_types import IDStr
from models_library.conversations import ConversationMessageType
from models_library.rest_ordering import OrderBy, OrderDirection
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.conversation_messages import conversation_messages
from simcore_postgres_database.models.users import users
from simcore_service_webserver.conversations import _conversation_message_repository
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.db.plugin import get_asyncpg_engine


@pytest.fixture
async def conversation_with_two_messages(
    client: TestClient,
    logged_user: UserInfoDict,
) -> str:
    assert client.app
    base_url = client.app.router["list_conversations"].url_for()
    resp = await client.post(f"{base_url}", json={"name": "Repo contract", "type": "SUPPORT"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    conversation_id = data["conversationId"]

    engine = get_asyncpg_engine(client.app)
    async with engine.connect() as conn:
        user_primary_gid = await conn.scalar(sa.select(users.c.primary_gid).where(users.c.id == logged_user["id"]))
    async with engine.begin() as conn:
        await conn.execute(
            conversation_messages.insert().values(
                [
                    {
                        "conversation_id": conversation_id,
                        "user_group_id": user_primary_gid,
                        "content": f"message {i + 1}",
                        "type": ConversationMessageType.MESSAGE,
                        "created": sa.func.now(),
                        "modified": sa.func.now(),
                    }
                    for i in range(2)
                ]
            )
        )
    return conversation_id


_ORDER_BY_CREATED_DESC = OrderBy(field=IDStr("created"), direction=OrderDirection.DESC)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_list_messages_total_independent_of_pagination(
    client: TestClient,
    conversation_with_two_messages: str,
):
    assert client.app

    total, items = await _conversation_message_repository.list_(
        client.app,
        conversation_id=conversation_with_two_messages,
        offset=0,
        limit=20,
        order_by=_ORDER_BY_CREATED_DESC,
    )
    assert total == 2
    assert len(items) == 2


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_list_messages_offset_past_total_returns_empty_page_with_real_total(
    client: TestClient,
    conversation_with_two_messages: str,
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
    assert total == 2
    assert items == []


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_list_messages_empty_conversation(
    client: TestClient,
    logged_user: UserInfoDict,
):
    assert client.app
    base_url = client.app.router["list_conversations"].url_for()
    resp = await client.post(f"{base_url}", json={"name": "Empty", "type": "SUPPORT"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)

    total, items = await _conversation_message_repository.list_(
        client.app,
        conversation_id=data["conversationId"],
        offset=0,
        limit=20,
        order_by=_ORDER_BY_CREATED_DESC,
    )
    assert total == 0
    assert items == []
