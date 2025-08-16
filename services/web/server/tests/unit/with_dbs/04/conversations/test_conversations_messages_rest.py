# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-statements


from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from http import HTTPStatus
from types import SimpleNamespace
from uuid import uuid4

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.conversations import (
    ConversationMessageRestGet,
)
from models_library.conversations import (
    ConversationMessageGetDB,
    ConversationMessageType,
)
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.conversations import _conversation_message_service
from simcore_service_webserver.db.models import UserRole


@pytest.fixture
def mock_functions_factory(
    mocker: MockerFixture,
) -> Callable[[Iterable[tuple[object, str]]], SimpleNamespace]:
    def _patch(targets_and_names: Iterable[tuple[object, str]]) -> SimpleNamespace:
        return SimpleNamespace(
            **{
                name: mocker.patch.object(target, name)
                for target, name in targets_and_names
            }
        )

    return _patch


@pytest.fixture
async def conversation_id(
    client: TestClient,
    logged_user: UserInfoDict,
) -> str:
    """Create a test conversation and return its ID"""
    assert client.app
    base_url = client.app.router["list_conversations"].url_for()
    body = {"name": "Test Support Conversation", "type": "SUPPORT"}
    resp = await client.post(f"{base_url}", json=body)
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    return data["conversationId"]


@pytest.mark.parametrize(
    "user_role,expected",
    [
        # (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_conversation_messages_user_role_access(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: HTTPStatus,
    conversation_id: str,
):
    """Test user role access to conversation messages endpoints"""
    assert client.app
    list_url = client.app.router["list_conversation_messages"].url_for(
        conversation_id=conversation_id
    )
    resp = await client.get(f"{list_url}")
    assert resp.status == 401 if user_role == UserRole.ANONYMOUS else 200


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, status.HTTP_201_CREATED),
    ],
)
async def test_conversation_messages_create_and_list(
    client: TestClient,
    logged_user: UserInfoDict,
    expected: HTTPStatus,
    conversation_id: str,
    mock_functions_factory: Callable[[Iterable[tuple[object, str]]], SimpleNamespace],
):
    """Test creating and listing messages in a support conversation"""
    mocks = mock_functions_factory(
        [
            (_conversation_message_service, "create_message"),
            (_conversation_message_service, "list_messages_for_conversation"),
        ]
    )

    # Mock the create_message function to return a message
    mock_message = ConversationMessageGetDB(
        message_id=uuid4(),
        conversation_id=uuid4(),  # Convert string to UUID
        user_group_id=1,  # Default primary group ID
        content="Test message content",
        type=ConversationMessageType.MESSAGE,
        created=datetime.now(tz=UTC),
        modified=datetime.now(tz=UTC),
    )
    mocks.create_message.return_value = mock_message

    assert client.app
    create_url = client.app.router["create_conversation_message"].url_for(
        conversation_id=conversation_id
    )

    # Test creating a message
    body = {"content": "Test message content", "type": "MESSAGE"}
    resp = await client.post(f"{create_url}", json=body)
    data, _ = await assert_status(resp, expected)
    assert ConversationMessageRestGet.model_validate(data)
    assert data["content"] == "Test message content"
    assert data["type"] == "MESSAGE"
    first_message_id = data["messageId"]

    assert mocks.create_message.call_count == 1

    # Mock the list_messages_for_conversation function
    mocks.list_messages_for_conversation.return_value = (1, [mock_message])

    # Test listing messages
    list_url = client.app.router["list_conversation_messages"].url_for(
        conversation_id=conversation_id
    )
    resp = await client.get(f"{list_url}")
    data, _, meta, links = await assert_status(
        resp,
        status.HTTP_200_OK,
        include_meta=True,
        include_links=True,
    )
    assert len(data) == 1
    assert meta["total"] == 1
    assert links

    assert mocks.list_messages_for_conversation.call_count == 1

    return first_message_id


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, status.HTTP_200_OK),
    ],
)
async def test_conversation_messages_get_update_delete(
    client: TestClient,
    logged_user: UserInfoDict,
    expected: HTTPStatus,
    conversation_id: str,
    mock_functions_factory: Callable[[Iterable[tuple[object, str]]], SimpleNamespace],
):
    """Test getting, updating, and deleting messages in a support conversation"""
    mocks = mock_functions_factory(
        [
            (_conversation_message_service, "create_message"),
            (_conversation_message_service, "get_message"),
            (_conversation_message_service, "update_message"),
            (_conversation_message_service, "delete_message"),
        ]
    )

    # Create a test message first
    message_id = uuid4()
    mock_message = ConversationMessageGetDB(
        message_id=message_id,
        conversation_id=uuid4(),  # Convert string to UUID
        user_group_id=1,  # Default primary group ID
        content="Original message content",
        type=ConversationMessageType.MESSAGE,
        created=datetime.now(tz=UTC),
        modified=datetime.now(tz=UTC),
    )
    mocks.create_message.return_value = mock_message

    assert client.app
    create_url = client.app.router["create_conversation_message"].url_for(
        conversation_id=conversation_id
    )

    # Create a message
    body = {"content": "Original message content", "type": "MESSAGE"}
    resp = await client.post(f"{create_url}", json=body)
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    created_message_id = data["messageId"]

    # Mock get_message
    mocks.get_message.return_value = mock_message

    # Test getting a specific message
    get_url = client.app.router["get_conversation_message"].url_for(
        conversation_id=conversation_id, message_id=created_message_id
    )
    resp = await client.get(f"{get_url}")
    data, _ = await assert_status(resp, expected)
    assert data["messageId"] == str(message_id)
    assert data["content"] == "Original message content"

    assert mocks.get_message.call_count == 1

    # Mock update_message
    updated_mock_message = ConversationMessageGetDB(
        message_id=message_id,
        conversation_id=uuid4(),  # Convert string to UUID
        user_group_id=1,  # Default primary group ID
        content="Updated message content",
        type=ConversationMessageType.MESSAGE,
        created=datetime.now(tz=UTC),
        modified=datetime.now(tz=UTC),
    )
    mocks.update_message.return_value = updated_mock_message

    # Test updating a message
    update_url = client.app.router["update_conversation_message"].url_for(
        conversation_id=conversation_id, message_id=created_message_id
    )
    updated_content = "Updated message content"
    resp = await client.put(
        f"{update_url}",
        json={"content": updated_content},
    )
    data, _ = await assert_status(resp, expected)
    assert data["content"] == updated_content

    assert mocks.update_message.call_count == 1

    # Test deleting a message
    delete_url = client.app.router["delete_conversation_message"].url_for(
        conversation_id=conversation_id, message_id=created_message_id
    )
    resp = await client.delete(f"{delete_url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    assert mocks.delete_message.call_count == 1


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_conversation_messages_pagination(
    client: TestClient,
    logged_user: UserInfoDict,
    conversation_id: str,
    mock_functions_factory: Callable[[Iterable[tuple[object, str]]], SimpleNamespace],
):
    """Test pagination of conversation messages list"""
    mocks = mock_functions_factory(
        [
            (_conversation_message_service, "list_messages_for_conversation"),
        ]
    )

    # Mock multiple messages
    mock_messages = []
    for i in range(5):
        mock_message = ConversationMessageGetDB(
            message_id=uuid4(),
            conversation_id=uuid4(),  # Convert string to UUID
            user_group_id=1,  # Default primary group ID
            content=f"Message {i+1}",
            type=ConversationMessageType.MESSAGE,
            created=datetime.now(tz=UTC),
            modified=datetime.now(tz=UTC),
        )
        mock_messages.append(mock_message)

    # Mock pagination with limit=3
    mocks.list_messages_for_conversation.return_value = (5, mock_messages[:3])

    assert client.app
    list_url = client.app.router["list_conversation_messages"].url_for(
        conversation_id=conversation_id
    )

    # Test pagination with limit
    resp = await client.get(f"{list_url}?limit=3")
    data, _, meta, links = await assert_status(
        resp,
        status.HTTP_200_OK,
        include_meta=True,
        include_links=True,
    )
    assert len(data) == 3
    assert meta["total"] == 5
    assert links

    assert mocks.list_messages_for_conversation.call_count == 1


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_conversation_messages_validation_errors(
    client: TestClient,
    logged_user: UserInfoDict,
    conversation_id: str,
):
    """Test validation errors for conversation messages"""
    assert client.app
    create_url = client.app.router["create_conversation_message"].url_for(
        conversation_id=conversation_id
    )

    # Test creating message with missing content
    body = {"type": "MESSAGE"}
    resp = await client.post(f"{create_url}", json=body)
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)

    # Test creating message with missing type
    body = {"content": "Test message"}
    resp = await client.post(f"{create_url}", json=body)
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)

    # Test creating message with invalid type
    body = {"content": "Test message", "type": "INVALID_TYPE"}
    resp = await client.post(f"{create_url}", json=body)
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)

    # Test creating message with empty content
    body = {"content": "", "type": "MESSAGE"}
    resp = await client.post(f"{create_url}", json=body)
    await assert_status(resp, status.HTTP_201_CREATED)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_conversation_messages_different_types(
    client: TestClient,
    logged_user: UserInfoDict,
    conversation_id: str,
    mock_functions_factory: Callable[[Iterable[tuple[object, str]]], SimpleNamespace],
):
    """Test creating messages with different message types"""
    mocks = mock_functions_factory(
        [
            (_conversation_message_service, "create_message"),
        ]
    )

    assert client.app
    create_url = client.app.router["create_conversation_message"].url_for(
        conversation_id=conversation_id
    )

    # Test USER_MESSAGE type
    user_message = ConversationMessageGetDB(
        message_id=uuid4(),
        conversation_id=uuid4(),  # Convert string to UUID
        user_group_id=1,  # Default primary group ID
        content="User message",
        type=ConversationMessageType.MESSAGE,
        created=datetime.now(tz=UTC),
        modified=datetime.now(tz=UTC),
    )
    mocks.create_message.return_value = user_message

    body = {"content": "User message", "type": "MESSAGE"}
    resp = await client.post(f"{create_url}", json=body)
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    assert data["type"] == "MESSAGE"

    # Test NOTIFICATION type
    system_message = ConversationMessageGetDB(
        message_id=uuid4(),
        conversation_id=uuid4(),  # Convert string to UUID
        user_group_id=1,  # Default primary group ID
        content="System message",
        type=ConversationMessageType.NOTIFICATION,
        created=datetime.now(tz=UTC),
        modified=datetime.now(tz=UTC),
    )
    mocks.create_message.return_value = system_message

    body = {"content": "System message", "type": "NOTIFICATION"}
    resp = await client.post(f"{create_url}", json=body)
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    assert data["type"] == "NOTIFICATION"

    assert mocks.create_message.call_count == 2


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_conversation_messages_nonexistent_resources(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_functions_factory: Callable[[Iterable[tuple[object, str]]], SimpleNamespace],
):
    """Test operations on nonexistent conversations and messages"""
    mocks = mock_functions_factory(
        [
            (_conversation_message_service, "get_message"),
            (_conversation_message_service, "update_message"),
            (_conversation_message_service, "delete_message"),
        ]
    )

    # Import the exception that should be raised
    from simcore_service_webserver.conversations.errors import (
        ConversationErrorNotFoundError,
    )

    # Mock service to raise ConversationErrorNotFoundError
    mocks.get_message.side_effect = ConversationErrorNotFoundError(
        conversation_id="nonexistent"
    )
    mocks.update_message.side_effect = ConversationErrorNotFoundError(
        conversation_id="nonexistent"
    )
    mocks.delete_message.side_effect = ConversationErrorNotFoundError(
        conversation_id="nonexistent"
    )

    nonexistent_conversation_id = "00000000-0000-0000-0000-000000000000"
    nonexistent_message_id = "00000000-0000-0000-0000-000000000001"

    assert client.app

    # Test getting message from nonexistent conversation
    get_url = client.app.router["get_conversation_message"].url_for(
        conversation_id=nonexistent_conversation_id, message_id=nonexistent_message_id
    )
    resp = await client.get(f"{get_url}")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)

    # Test updating message in nonexistent conversation
    update_url = client.app.router["update_conversation_message"].url_for(
        conversation_id=nonexistent_conversation_id, message_id=nonexistent_message_id
    )
    resp = await client.put(f"{update_url}", json={"content": "Updated content"})
    await assert_status(resp, status.HTTP_404_NOT_FOUND)

    # Test deleting message from nonexistent conversation
    delete_url = client.app.router["delete_conversation_message"].url_for(
        conversation_id=nonexistent_conversation_id, message_id=nonexistent_message_id
    )
    resp = await client.delete(f"{delete_url}")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)
