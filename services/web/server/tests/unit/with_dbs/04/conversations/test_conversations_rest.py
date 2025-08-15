# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-statements


from collections.abc import Callable, Iterable
from http import HTTPStatus
from types import SimpleNamespace

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.conversations import ConversationRestGet
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import LoggedUser, UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.conversations import _conversation_service
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


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_conversations_user_role_access(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: HTTPStatus,
):
    assert client.app
    base_url = client.app.router["list_conversations"].url_for()
    resp = await client.get(f"{base_url}?type=SUPPORT")
    assert resp.status == 401 if user_role == UserRole.ANONYMOUS else 200


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize(
    "conversation_type,expected_status",
    [
        ("SUPPORT", status.HTTP_200_OK),
        ("PROJECT_STATIC", status.HTTP_422_UNPROCESSABLE_ENTITY),
        ("PROJECT_ANNOTATION", status.HTTP_422_UNPROCESSABLE_ENTITY),
    ],
)
async def test_list_conversations_type_validation(
    client: TestClient,
    logged_user: UserInfoDict,
    conversation_type: str,
    expected_status: HTTPStatus,
):
    """Test that only SUPPORT type conversations are allowed"""
    assert client.app
    base_url = client.app.router["list_conversations"].url_for()
    resp = await client.get(f"{base_url}?type={conversation_type}")
    if expected_status == status.HTTP_200_OK:
        await assert_status(resp, expected_status)
    else:
        # Should get validation error for non-SUPPORT types
        assert resp.status == expected_status


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/private-issues/issues/51"
)
@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, status.HTTP_200_OK),
    ],
)
async def test_conversations_create_and_list(
    client: TestClient,
    logged_user: UserInfoDict,
    expected: HTTPStatus,
    mock_functions_factory: Callable[[Iterable[tuple[object, str]]], SimpleNamespace],
):
    """Test creating and listing support conversations"""
    mocks = mock_functions_factory(
        [
            (_conversation_service, "notify_conversation_created"),
        ]
    )

    base_url = client.app.router["list_conversations"].url_for()

    # Test listing empty conversations initially
    resp = await client.get(f"{base_url}?type=SUPPORT")
    data, _, meta, links = await assert_status(
        resp,
        expected,
        include_meta=True,
        include_links=True,
    )
    assert data == []
    assert meta["total"] == 0
    assert links

    # Test creating a support conversation
    body = {"name": "Support Request - Bug Report", "type": "SUPPORT"}
    resp = await client.post(f"{base_url}", json=body)
    data, _ = await assert_status(
        resp,
        status.HTTP_201_CREATED,
    )
    assert ConversationRestGet.model_validate(data)
    first_conversation_id = data["conversationId"]
    assert data["name"] == "Support Request - Bug Report"
    assert data["type"] == "SUPPORT"

    assert mocks.notify_conversation_created.call_count == 0

    # Test creating a second support conversation
    body = {"name": "Support Request - Feature Request", "type": "SUPPORT"}
    resp = await client.post(f"{base_url}", json=body)
    data, _ = await assert_status(
        resp,
        status.HTTP_201_CREATED,
    )
    assert ConversationRestGet.model_validate(data)
    second_conversation_id = data["conversationId"]

    assert mocks.notify_conversation_created.call_count == 0

    # Test creating conversation with invalid type should fail
    body = {"name": "Invalid Type", "type": "PROJECT_STATIC"}
    resp = await client.post(f"{base_url}", json=body)
    await assert_status(resp, status.HTTP_400_BAD_REQUEST)

    # Test listing all conversations
    resp = await client.get(f"{base_url}?type=SUPPORT")
    data, _, meta, links = await assert_status(
        resp,
        expected,
        include_meta=True,
        include_links=True,
    )
    assert len(data) == 2
    assert meta["total"] == 2
    assert links

    return first_conversation_id, second_conversation_id


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/private-issues/issues/51"
)
@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, status.HTTP_200_OK),
    ],
)
async def test_conversations_update_and_delete(
    client: TestClient,
    logged_user: UserInfoDict,
    expected: HTTPStatus,
    mock_functions_factory: Callable[[Iterable[tuple[object, str]]], SimpleNamespace],
):
    """Test updating and deleting support conversations"""
    mocks = mock_functions_factory(
        [
            (_conversation_service, "notify_conversation_created"),
            (_conversation_service, "notify_conversation_updated"),
            (_conversation_service, "notify_conversation_deleted"),
        ]
    )

    base_url = client.app.router["list_conversations"].url_for()

    # Create a conversation first
    body = {"name": "Support Request - Bug Report", "type": "SUPPORT"}
    resp = await client.post(f"{base_url}", json=body)
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    first_conversation_id = data["conversationId"]

    # Test getting a specific conversation
    get_url = client.app.router["get_conversation"].url_for(
        conversation_id=first_conversation_id
    )
    resp = await client.get(f"{get_url}?type=SUPPORT")
    data, _ = await assert_status(resp, expected)
    assert data["conversationId"] == first_conversation_id
    assert data["name"] == "Support Request - Bug Report"

    # Test updating a conversation
    update_url = client.app.router["update_conversation"].url_for(
        conversation_id=first_conversation_id
    )
    updated_name = "Updated Support Request - Bug Report"
    resp = await client.put(
        f"{update_url}?type=SUPPORT",
        json={"name": updated_name},
    )
    data, _ = await assert_status(resp, expected)
    assert data["name"] == updated_name

    assert mocks.notify_conversation_updated.call_count == 0

    # Verify the update by getting the conversation again
    resp = await client.get(f"{get_url}?type=SUPPORT")
    data, _ = await assert_status(resp, expected)
    assert data["name"] == updated_name

    # Test deleting a conversation
    delete_url = client.app.router["delete_conversation"].url_for(
        conversation_id=first_conversation_id
    )
    resp = await client.delete(f"{delete_url}?type=SUPPORT")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    assert mocks.notify_conversation_deleted.call_count == 0

    # Verify deletion by listing conversations
    resp = await client.get(f"{base_url}?type=SUPPORT")
    data, _, meta = await assert_status(resp, expected, include_meta=True)
    assert len(data) == 0
    assert meta["total"] == 0

    # Test getting deleted conversation should fail
    resp = await client.get(f"{get_url}?type=SUPPORT")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_conversations_with_extra_context(
    client: TestClient,
    logged_user: UserInfoDict,
):
    """Test creating conversation with extra context"""
    base_url = client.app.router["list_conversations"].url_for()

    # Test creating a support conversation with extra context
    body = {
        "name": "Support Request with Context",
        "type": "SUPPORT",
        "extraContext": {
            "issue_type": "bug",
            "priority": "high",
            "browser": "Chrome",
            "version": "1.0.0",
        },
    }
    resp = await client.post(f"{base_url}", json=body)
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    assert ConversationRestGet.model_validate(data)
    assert data["name"] == "Support Request with Context"
    assert data["type"] == "SUPPORT"
    assert data["extraContext"] == {
        "issue_type": "bug",
        "priority": "high",
        "browser": "Chrome",
        "version": "1.0.0",
    }


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_conversations_pagination(
    client: TestClient,
    logged_user: UserInfoDict,
):
    """Test pagination of conversations list"""
    base_url = client.app.router["list_conversations"].url_for()

    # Create multiple conversations
    for i in range(5):
        body = {"name": f"Support Request {i+1}", "type": "SUPPORT"}
        resp = await client.post(f"{base_url}", json=body)
        await assert_status(resp, status.HTTP_201_CREATED)

    # Test pagination with limit
    resp = await client.get(f"{base_url}?type=SUPPORT&limit=3")
    data, _, meta, links = await assert_status(
        resp,
        status.HTTP_200_OK,
        include_meta=True,
        include_links=True,
    )
    assert len(data) == 3
    assert meta["total"] == 5
    assert links

    # Test pagination with offset
    resp = await client.get(f"{base_url}?type=SUPPORT&limit=3&offset=3")
    data, _, meta = await assert_status(
        resp,
        status.HTTP_200_OK,
        include_meta=True,
    )
    assert len(data) == 2  # Remaining items
    assert meta["total"] == 5


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_conversations_access_control(
    client: TestClient,
    logged_user: UserInfoDict,
):
    """Test that users can only access their own support conversations"""
    base_url = client.app.router["list_conversations"].url_for()

    # Create a conversation as first user
    body = {"name": "User 1 Support Request", "type": "SUPPORT"}
    resp = await client.post(f"{base_url}", json=body)
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    conversation_id = data["conversationId"]

    # Login as a different user
    async with LoggedUser(client):
        # The new user should not see the first user's conversation
        resp = await client.get(f"{base_url}?type=SUPPORT")
        data, _, meta = await assert_status(
            resp,
            status.HTTP_200_OK,
            include_meta=True,
        )
        assert len(data) == 0
        assert meta["total"] == 0

        # The new user should not be able to access the specific conversation
        get_url = client.app.router["get_conversation"].url_for(
            conversation_id=conversation_id
        )
        resp = await client.get(f"{get_url}?type=SUPPORT")
        await assert_status(resp, status.HTTP_404_NOT_FOUND)

        # The new user should not be able to update the conversation
        update_url = client.app.router["update_conversation"].url_for(
            conversation_id=conversation_id
        )
        resp = await client.put(
            f"{update_url}?type=SUPPORT",
            json={"name": "Unauthorized update attempt"},
        )
        await assert_status(resp, status.HTTP_404_NOT_FOUND)

        # The new user should not be able to delete the conversation
        delete_url = client.app.router["delete_conversation"].url_for(
            conversation_id=conversation_id
        )
        resp = await client.delete(f"{delete_url}?type=SUPPORT")
        await assert_status(resp, status.HTTP_404_NOT_FOUND)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_conversations_error_handling(
    client: TestClient,
    logged_user: UserInfoDict,
):
    """Test error handling for conversations endpoints"""
    base_url = client.app.router["list_conversations"].url_for()

    # Test creating conversation with missing required fields
    resp = await client.post(f"{base_url}", json={})
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)

    # Test creating conversation with invalid type
    body = {"name": "Invalid Type Request", "type": "INVALID_TYPE"}
    resp = await client.post(f"{base_url}", json=body)
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)

    # Test operations on non-existent conversation
    fake_conversation_id = "00000000-0000-0000-0000-000000000000"

    get_url = client.app.router["get_conversation"].url_for(
        conversation_id=fake_conversation_id
    )
    resp = await client.get(f"{get_url}?type=SUPPORT")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)

    update_url = client.app.router["update_conversation"].url_for(
        conversation_id=fake_conversation_id
    )
    resp = await client.put(
        f"{update_url}?type=SUPPORT",
        json={"name": "Update non-existent"},
    )
    await assert_status(resp, status.HTTP_404_NOT_FOUND)

    delete_url = client.app.router["delete_conversation"].url_for(
        conversation_id=fake_conversation_id
    )
    resp = await client.delete(f"{delete_url}?type=SUPPORT")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_conversations_without_type_query_param(
    client: TestClient,
    logged_user: UserInfoDict,
):
    """Test that endpoints require type query parameter"""
    base_url = client.app.router["list_conversations"].url_for()

    # Create a conversation first
    body = {"name": "Test Conversation", "type": "SUPPORT"}
    resp = await client.post(f"{base_url}", json=body)
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    conversation_id = data["conversationId"]

    # Test endpoints without type parameter should fail
    resp = await client.get(f"{base_url}")
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)

    get_url = client.app.router["get_conversation"].url_for(
        conversation_id=conversation_id
    )
    resp = await client.get(f"{get_url}")
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)

    update_url = client.app.router["update_conversation"].url_for(
        conversation_id=conversation_id
    )
    resp = await client.put(f"{update_url}", json={"name": "Updated"})
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)

    delete_url = client.app.router["delete_conversation"].url_for(
        conversation_id=conversation_id
    )
    resp = await client.delete(f"{delete_url}")
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)
