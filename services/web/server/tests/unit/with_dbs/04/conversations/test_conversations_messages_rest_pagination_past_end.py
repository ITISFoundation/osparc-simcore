# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""Regression test for the past-the-end pagination contract.

A client asking for a page that does not exist (``offset >= total``) -- e.g. after
following a stale ``next`` link, or after rows were deleted -- used to get an HTTP 500:
``PageMetaInfoLimitOffset`` rejected ``offset >= total`` and the ``ValidationError``
surfaced as the generic error page.

The contract is now lenient (REST-conventional): such a request returns HTTP 200 with an
empty ``data`` carrying the *real* ``total``, ``count == 0``, and self-consistent links
(``next`` null, ``last`` pointing at a page that exists). The repository layer already
returned truth (real total, empty page); this asserts it reaches the client.
"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Final
from uuid import UUID

import pytest
from aiohttp.test_utils import TestClient
from models_library.conversations import ConversationID, ConversationMessageType
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.conversation_messages import conversation_messages
from simcore_service_webserver.db.models import UserRole
from sqlalchemy.ext.asyncio import AsyncEngine
from yarl import URL


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


_NUMBER_OF_MESSAGES: Final = 2


@pytest.fixture
async def conversation_id(
    client: TestClient,
    logged_user: UserInfoDict,
) -> ConversationID:
    assert client.app
    url = client.app.router["list_conversations"].url_for()
    resp = await client.post(f"{url}", json={"name": "Past-the-end", "type": "SUPPORT"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    return UUID(data["conversationId"])


@pytest.fixture
async def conversation_with_two_messages(
    client: TestClient,
    asyncpg_engine: AsyncEngine,
    logged_user: UserInfoDict,
    conversation_id: ConversationID,
) -> AsyncIterator[ConversationID]:
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


async def test_list_messages_offset_past_total_returns_200_empty_page(
    client: TestClient,
    conversation_with_two_messages: ConversationID,
):
    """offset far past the end -> 200, empty page, real total (was HTTP 500)"""
    assert client.app
    list_url = client.app.router["list_conversation_messages"].url_for(
        conversation_id=f"{conversation_with_two_messages}"
    )
    resp = await client.get(list_url.with_query({"offset": 100}))
    data, _, meta, links = await assert_status(resp, status.HTTP_200_OK, include_meta=True, include_links=True)

    assert data == []
    assert meta["total"] == _NUMBER_OF_MESSAGES
    assert meta["count"] == 0
    assert meta["offset"] == 100
    # links must be self-consistent: no next, and no negative offset anywhere
    assert links["next"] is None
    for link in (links["self"], links["first"], links["prev"], links["last"]):
        if link is not None:
            assert int(URL(link).query["offset"]) >= 0


async def test_list_messages_offset_equal_to_total_returns_200_empty_page(
    client: TestClient,
    conversation_with_two_messages: ConversationID,
):
    """the boundary offset == total is also a valid empty page"""
    assert client.app
    list_url = client.app.router["list_conversation_messages"].url_for(
        conversation_id=f"{conversation_with_two_messages}"
    )
    resp = await client.get(list_url.with_query({"offset": _NUMBER_OF_MESSAGES}))
    data, _, meta, _links = await assert_status(resp, status.HTTP_200_OK, include_meta=True, include_links=True)

    assert data == []
    assert meta["total"] == _NUMBER_OF_MESSAGES
    assert meta["count"] == 0


async def test_list_messages_empty_conversation_offset_past_returns_200(
    client: TestClient,
    conversation_id: ConversationID,
):
    """a zero-item collection at a non-zero offset is a valid empty page (was HTTP 500)"""
    assert client.app
    list_url = client.app.router["list_conversation_messages"].url_for(conversation_id=f"{conversation_id}")
    resp = await client.get(list_url.with_query({"offset": 10}))
    data, _, meta, links = await assert_status(resp, status.HTTP_200_OK, include_meta=True, include_links=True)

    assert data == []
    assert meta["total"] == 0
    assert meta["count"] == 0
    assert links["next"] is None
    # last link must not carry a negative offset for an empty collection
    assert int(URL(links["last"]).query["offset"]) == 0
