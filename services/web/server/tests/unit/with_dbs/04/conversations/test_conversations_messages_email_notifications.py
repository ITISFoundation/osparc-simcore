# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from aiohttp import web
from models_library.conversations import (
    ConversationGetDB,
    ConversationType,
    ConversationUserType,
)
from models_library.notifications import Channel
from pydantic import HttpUrl
from simcore_service_webserver.conversations._conversation_message_service import (
    _notify_support_reply_via_email,
)


@pytest.fixture
def mock_app() -> web.Application:
    return web.Application()


@pytest.fixture
def sample_conversation() -> ConversationGetDB:
    return ConversationGetDB(
        conversation_id=uuid4(),
        name="Test Support Conversation",
        project_uuid=None,
        user_group_id=1,
        type=ConversationType.SUPPORT,
        product_name="osparc",
        extra_context={},
        fogbugz_case_id=None,
        is_read_by_user=True,
        is_read_by_support=False,
        last_message_created_at=datetime.now(tz=UTC),
        created=datetime.now(tz=UTC),
        modified=datetime.now(tz=UTC),
    )


@pytest.mark.parametrize(
    "conversation_user_type",
    [
        ConversationUserType.SUPPORT_USER,
        ConversationUserType.CHATBOT_USER,
    ],
)
async def test_notify_support_reply_via_email_to_user(
    mock_app: web.Application,
    sample_conversation: ConversationGetDB,
    conversation_user_type: ConversationUserType,
):
    """When support/chatbot replies, the conversation creator (regular user) should be notified."""
    sender_user_id = 100
    mock_product = AsyncMock()
    mock_product.base_url = HttpUrl("https://test.osparc.io/")
    mock_product.support_standard_group_id = 5

    with (
        patch(
            "simcore_service_webserver.conversations._conversation_message_service.products_service.get_product",
            return_value=mock_product,
        ),
        patch(
            "simcore_service_webserver.conversations._conversation_message_service.users_service.get_user",
            new_callable=AsyncMock,
            # Recipient user (conversation creator)
            return_value={"first_name": "John", "last_name": "Doe", "email": "john@test.io", "username": "johndoe"},
        ),
        patch(
            "simcore_service_webserver.conversations._conversation_message_service.users_service.get_user_id_from_gid",
            new_callable=AsyncMock,
            return_value=200,
        ),
        patch(
            "simcore_service_webserver.conversations._conversation_message_service.notifications_service.send_message_from_template",
            new_callable=AsyncMock,
        ) as mock_send,
    ):
        await _notify_support_reply_via_email(
            mock_app,
            product_name="osparc",
            conversation=sample_conversation,
            conversation_user_type=conversation_user_type,
            message_content="Hello, here is the answer to your question.",
            sender_user_id=sender_user_id,
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["channel"] == Channel.email
        assert call_kwargs["template_name"] == "support_reply"
        assert call_kwargs["group_ids"] is None
        assert len(call_kwargs["external_contacts"]) == 1
        assert call_kwargs["external_contacts"][0].email == "john@test.io"
        assert call_kwargs["context"]["user"]["first_name"] == "John"
        assert call_kwargs["context"]["user"]["user_name"] == "johndoe"
        assert call_kwargs["context"]["message_content"] == "Hello, here is the answer to your question."


async def test_notify_support_reply_via_email_to_support_group(
    mock_app: web.Application,
    sample_conversation: ConversationGetDB,
):
    """When a regular user replies, the support group should be notified."""
    sender_user_id = 200
    mock_product = AsyncMock()
    mock_product.base_url = HttpUrl("https://test.osparc.io/")
    mock_product.support_standard_group_id = 5

    with (
        patch(
            "simcore_service_webserver.conversations._conversation_message_service.products_service.get_product",
            return_value=mock_product,
        ),
        patch(
            "simcore_service_webserver.conversations._conversation_message_service.users_service.get_user",
            new_callable=AsyncMock,
            return_value={"first_name": "John", "last_name": "Doe", "email": "john@test.io"},
        ),
        patch(
            "simcore_service_webserver.conversations._conversation_message_service.notifications_service.send_message_from_template",
            new_callable=AsyncMock,
        ) as mock_send,
    ):
        await _notify_support_reply_via_email(
            mock_app,
            product_name="osparc",
            conversation=sample_conversation,
            conversation_user_type=ConversationUserType.REGULAR_USER,
            message_content="I still have an issue.",
            sender_user_id=sender_user_id,
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["channel"] == Channel.email
        assert call_kwargs["template_name"] == "support_reply"
        assert call_kwargs["group_ids"] == [5]
        assert call_kwargs["external_contacts"] is None
        assert call_kwargs["context"]["recipient_name"] == "Support Team"
        assert call_kwargs["context"]["sender_name"] == "John Doe"
        assert call_kwargs["context"]["message_content"] == "I still have an issue."


async def test_notify_support_reply_via_email_no_support_group(
    mock_app: web.Application,
    sample_conversation: ConversationGetDB,
):
    """When a regular user replies but no support group is configured, no email is sent."""
    sender_user_id = 200
    mock_product = AsyncMock()
    mock_product.base_url = HttpUrl("https://test.osparc.io/")
    mock_product.support_standard_group_id = None

    with (
        patch(
            "simcore_service_webserver.conversations._conversation_message_service.products_service.get_product",
            return_value=mock_product,
        ),
        patch(
            "simcore_service_webserver.conversations._conversation_message_service.users_service.get_user",
            new_callable=AsyncMock,
            return_value={"first_name": "John", "last_name": "Doe", "email": "john@test.io"},
        ),
        patch(
            "simcore_service_webserver.conversations._conversation_message_service.notifications_service.send_message_from_template",
            new_callable=AsyncMock,
        ) as mock_send,
    ):
        await _notify_support_reply_via_email(
            mock_app,
            product_name="osparc",
            conversation=sample_conversation,
            conversation_user_type=ConversationUserType.REGULAR_USER,
            message_content="I still have an issue.",
            sender_user_id=sender_user_id,
        )

        mock_send.assert_not_called()
