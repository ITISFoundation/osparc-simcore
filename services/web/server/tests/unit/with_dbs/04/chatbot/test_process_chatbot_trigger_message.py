# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


import json

import pytest
import respx
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.conversations import (
    ConversationGetDB,
    ConversationMessageGetDB,
    ConversationMessageType,
)
from models_library.groups import GroupMember
from models_library.rabbitmq_messages import WebserverChatbotRabbitMessage
from pydantic import TypeAdapter
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_service_webserver.chatbot import _process_chatbot_trigger_service
from simcore_service_webserver.chatbot._client import Message
from simcore_service_webserver.chatbot._process_chatbot_trigger_service import (
    _process_chatbot_trigger_message,
)
from simcore_service_webserver.conversations import conversations_service


@pytest.fixture
def mocked_conversations_service(
    mocker: MockerFixture,
    user: UserInfoDict,
    chatbot_user: UserInfoDict,
    support_team_user: UserInfoDict,
    faker: Faker,
) -> dict:
    # Mock message objects with content attribute
    conversation_id = faker.uuid4()
    mock_message_1 = ConversationMessageGetDB(
        message_id=faker.uuid4(),
        user_group_id=int(user["primary_gid"]),
        conversation_id=conversation_id,
        content="Hello, I need help with my simulation",
        type=ConversationMessageType.MESSAGE,
        created=faker.date_time_this_year(),
        modified=faker.date_time_this_year(),
    )

    mock_message_2 = ConversationMessageGetDB(
        message_id=faker.uuid4(),
        user_group_id=int(support_team_user["primary_gid"]),
        conversation_id=conversation_id,
        content="Great, I will let the bot help you.",
        type=ConversationMessageType.MESSAGE,
        created=faker.date_time_this_year(),
        modified=faker.date_time_this_year(),
    )

    mock_message_3 = ConversationMessageGetDB(
        message_id=faker.uuid4(),
        user_group_id=int(chatbot_user["primary_gid"]),
        conversation_id=conversation_id,
        content="Sure, I'd be happy to help you with that.",
        type=ConversationMessageType.MESSAGE,
        created=faker.date_time_this_year(),
        modified=faker.date_time_this_year(),
    )

    mock_message_4 = ConversationMessageGetDB(
        message_id=faker.uuid4(),
        user_group_id=int(user["primary_gid"]),
        conversation_id=conversation_id,
        content="It's not working properly",
        type=ConversationMessageType.MESSAGE,
        created=faker.date_time_this_year(),
        modified=faker.date_time_this_year(),
    )

    mock_messages = [mock_message_1, mock_message_2, mock_message_3, mock_message_4]

    # Mock list_messages_for_conversation with correct async signature
    async def _mock_list_messages(app, *, conversation_id, offset=0, limit=20, order_by=None):
        # Ensure all queries are done in descending order by created timestamp
        assert order_by is not None, "order_by parameter must be provided"
        assert order_by.field == "created", f"Expected order_by.field='created', got '{order_by.field}'"
        assert order_by.direction.value == "desc", (
            f"Expected order_by.direction='desc', got '{order_by.direction.value}'"
        )

        # Return messages sorted by created timestamp in descending order (newest first)
        # The implementation will reverse this list to get ascending order
        sorted_messages = sorted(mock_messages, key=lambda msg: msg.created, reverse=True)
        return (len(sorted_messages), sorted_messages)

    list_messages_mock = mocker.patch.object(
        conversations_service, "list_messages_for_conversation", side_effect=_mock_list_messages
    )

    # Mock create_support_message
    create_message_mock = mocker.patch.object(conversations_service, "create_support_message")

    return {
        "list_messages": list_messages_mock,
        "create_message": create_message_mock,
        "mock_messages": mock_messages,
    }


@pytest.fixture
async def mocked_list_groups_members(mocker: MockerFixture, support_team_user: UserInfoDict) -> MockType:
    mocked_list_group_members = mocker.patch.object(_process_chatbot_trigger_service, "list_group_members")
    mocked_list_group_members.return_value = [
        GroupMember(
            id=support_team_user["id"],
            primary_gid=int(support_team_user["primary_gid"]),
            name=support_team_user["name"],
            first_name=support_team_user.get("first_name"),
            last_name=support_team_user.get("last_name"),
            email=support_team_user["email"],
        )
    ]
    return mocked_list_group_members


async def test_process_chatbot_trigger_message(
    app_environment: EnvVarsDict,
    client: TestClient,
    user: UserInfoDict,
    mocked_get_current_product: MockType,
    mocked_list_groups_members: MockType,
    mocked_chatbot_api: respx.MockRouter,
    mocked_conversations_service: dict,
):
    assert client.app

    # Prepare message to bytes for processing
    _conversation = ConversationGetDB.model_json_schema()["examples"][0]
    _conversation["user_group_id"] = user["primary_gid"]
    _message = WebserverChatbotRabbitMessage(
        conversation=_conversation,
        last_message_id="42838344-03de-4ce2-8d93-589a5dcdfd05",
    )
    assert _message

    message_bytes = _message.model_dump_json().encode()

    # This is the function under test
    await _process_chatbot_trigger_message(app=client.app, data=message_bytes)

    # Assert that the necessary service calls were made
    # NOTE: list_messages is called twice - once with limit=1 and once with limit=20
    assert mocked_conversations_service["list_messages"].call_count == 1

    # Verify ALL messages queries were made in descending order by creation timestamp
    for call_args in mocked_conversations_service["list_messages"].call_args_list:
        assert call_args.kwargs["order_by"] is not None
        assert call_args.kwargs["order_by"].field == "created"
        assert call_args.kwargs["order_by"].direction.value == "desc"

    assert mocked_chatbot_api.calls.call_count == 1
    _last_request_content = mocked_chatbot_api.calls.last.request.content.decode("utf-8")
    messages_received_by_chatbot = TypeAdapter(list[Message]).validate_python(
        json.loads(_last_request_content).get("messages")
    )
    messages_received_by_chatbot = [msg for msg in messages_received_by_chatbot if msg.role != "developer"]

    # Verify that messages are passed to chatbot in ascending order (chronologically oldest first)
    # Get the mock messages sorted by creation time (ascending order)
    sorted_mock_messages = sorted(mocked_conversations_service["mock_messages"], key=lambda msg: msg.created)

    # Verify messages are present ascending order (latest last)
    for conversation_msg, chatbot_msg in zip(sorted_mock_messages, messages_received_by_chatbot, strict=True):
        assert conversation_msg.content == chatbot_msg.content

    mocked_conversations_service["create_message"].assert_called_once()
    mocked_list_groups_members.assert_called_once()
