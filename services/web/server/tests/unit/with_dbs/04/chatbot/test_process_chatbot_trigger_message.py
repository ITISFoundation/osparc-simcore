# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


import pytest
import respx
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.conversations import (
    ConversationGetDB,
    ConversationMessageGetDB,
    ConversationMessageType,
)
from models_library.rabbitmq_messages import WebserverChatbotRabbitMessage
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_service_webserver.chatbot._process_chatbot_trigger_service import (
    _process_chatbot_trigger_message,
)
from simcore_service_webserver.conversations import conversations_service


@pytest.fixture
def mocked_conversations_service(
    mocker: MockerFixture, user: UserInfoDict, chatbot_user: UserInfoDict, faker: Faker
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
        user_group_id=int(chatbot_user["primary_gid"]),
        conversation_id=conversation_id,
        content="Sure, I'd be happy to help you with that.",
        type=ConversationMessageType.MESSAGE,
        created=faker.date_time_this_year(),
        modified=faker.date_time_this_year(),
    )

    mock_message_3 = ConversationMessageGetDB(
        message_id=faker.uuid4(),
        user_group_id=int(user["primary_gid"]),
        conversation_id=conversation_id,
        content="It's not working properly",
        type=ConversationMessageType.MESSAGE,
        created=faker.date_time_this_year(),
        modified=faker.date_time_this_year(),
    )

    mock_messages = [mock_message_1, mock_message_2, mock_message_3]

    # Mock list_messages_for_conversation
    list_messages_mock = mocker.patch.object(
        conversations_service, "list_messages_for_conversation"
    )
    list_messages_mock.return_value = (len(mock_messages), mock_messages)

    # Mock create_support_message
    create_message_mock = mocker.patch.object(
        conversations_service, "create_support_message"
    )

    return {
        "list_messages": list_messages_mock,
        "create_message": create_message_mock,
        "mock_messages": mock_messages,
    }


async def test_process_chatbot_trigger_message(
    app_environment: EnvVarsDict,
    client: TestClient,
    user: UserInfoDict,
    mocked_get_current_product: MockType,
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
    mocked_conversations_service["list_messages"].assert_called_once()

    assert mocked_chatbot_api.calls.call_count == 1
    _last_request_content = mocked_chatbot_api.calls.last.request.content.decode(
        "utf-8"
    )
    assert "Hello, I need help with my simulation" in _last_request_content
    assert "Sure, I'd be happy to help you with that." in _last_request_content
    assert "It's not working properly" in _last_request_content

    mocked_conversations_service["create_message"].assert_called_once()
