# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""Regression test for the read-skew race in ``list_messages_for_conversation``.

The repository used to run the total-count query and the page query as **two
separate statements** in the same (READ COMMITTED) transaction. PostgreSQL takes
a fresh snapshot per statement, so a message committed by another transaction
*between* the two statements makes ``count > total`` and the REST handler dies
with a ``pydantic.ValidationError`` in ``PageMetaInfoLimitOffset`` (HTTP 500).

This test makes the race deterministic by hooking the page query (``AsyncConnection.stream``,
executed right *after* the total-count query in the buggy code) and inserting+committing a
message from a *second* connection just before the page query runs. In the buggy code the
count already snapshotted the older state, so the page then shows a row the count did not.
"""

from uuid import UUID

import pytest
from aiohttp.test_utils import TestClient
from models_library.conversations import ConversationID, ConversationMessageType
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.conversation_messages import conversation_messages
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from sqlalchemy.ext.asyncio import AsyncConnection


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


@pytest.fixture
async def conversation_id(
    client: TestClient,
    logged_user: UserInfoDict,
) -> ConversationID:
    """Create a test support conversation and return its ID"""
    assert client.app
    base_url = client.app.router["list_conversations"].url_for()
    resp = await client.post(f"{base_url}", json={"name": "Race Test", "type": "SUPPORT"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    return UUID(data["conversationId"])


async def test_list_messages_concurrent_insert_between_count_and_page(
    client: TestClient,
    logged_user: UserInfoDict,
    conversation_id: ConversationID,
    mocker: MockerFixture,
):
    """A message committed while listing must never yield count > total (HTTP 500)

    Before the fix this returned HTTP 500 (ValidationError: "count 1 bigger than
    expected total 0"). After the fix the page must be self-consistent: 200 with
    the raced message included and total >= count.
    """
    assert client.app
    engine = get_asyncpg_engine(client.app)
    user_primary_gid = int(logged_user["primary_gid"])

    original_stream = AsyncConnection.stream
    original_execute = AsyncConnection.execute
    race_armed = True

    async def _insert_committed_message() -> None:
        async with engine.begin() as other_conn:  # separate connection -> commits immediately
            await other_conn.execute(
                conversation_messages.insert().values(
                    conversation_id=conversation_id,
                    user_group_id=user_primary_gid,
                    content="message committed mid-request",
                    type=ConversationMessageType.MESSAGE,
                )
            )

    async def _commit_message_before_paged_query(original, self: AsyncConnection, statement, *args, **kwargs):
        nonlocal race_armed
        statement_str = str(statement)
        is_messages_paged_query = race_armed and "conversation_messages" in statement_str and "LIMIT" in statement_str
        if is_messages_paged_query:
            race_armed = False
            # commit right BEFORE the paged query runs: in the buggy two-statement
            # implementation the separate total-count had already snapshotted the older
            # state, making the page show a row the count did not see (count > total).
            # In the single-statement implementation the count shares the page's snapshot,
            # so the raced row is consistently reflected in both.
            await _insert_committed_message()
        return await original(self, statement, *args, **kwargs)

    # hook both entry points: the buggy implementation streamed the page via
    # ``stream`` after counting via ``scalar``; the fixed one runs a single statement
    # via ``execute``. Either way the committed insert lands mid-request.
    mocker.patch.object(
        AsyncConnection,
        "stream",
        new=lambda self, statement, *a, **kw: _commit_message_before_paged_query(
            original_stream, self, statement, *a, **kw
        ),
    )
    mocker.patch.object(
        AsyncConnection,
        "execute",
        new=lambda self, statement, *a, **kw: _commit_message_before_paged_query(
            original_execute, self, statement, *a, **kw
        ),
    )

    list_url = client.app.router["list_conversation_messages"].url_for(conversation_id=f"{conversation_id}")
    resp = await client.get(f"{list_url}")
    data, _, meta, _links = await assert_status(resp, status.HTTP_200_OK, include_meta=True, include_links=True)

    # the raced message is visible and the page metadata is consistent
    assert len(data) == 1
    assert meta["total"] >= len(data)
    assert data[0]["content"] == "message committed mid-request"
