# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-statements


from collections.abc import Callable, Iterable
from http import HTTPStatus
from types import SimpleNamespace
from uuid import UUID

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.conversations import ConversationRestGet
from models_library.products import ProductName
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import LoggedUser, UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.conversations import conversations
from simcore_postgres_database.utils_repos import transaction_context
from simcore_service_webserver.conversations import _conversation_service
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def mock_functions_factory(
    mocker: MockerFixture,
) -> Callable[[Iterable[tuple[object, str]]], SimpleNamespace]:
    def _patch(targets_and_names: Iterable[tuple[object, str]]) -> SimpleNamespace:
        return SimpleNamespace(**{name: mocker.patch.object(target, name) for target, name in targets_and_names})

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


@pytest.mark.acceptance_test("https://github.com/ITISFoundation/private-issues/issues/51")
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
            (_conversation_service, "notify_via_socket_conversation_created"),
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

    assert mocks.notify_via_socket_conversation_created.call_count == 1

    # Test creating a second support conversation
    body = {"name": "Support Request - Feature Request", "type": "SUPPORT"}
    resp = await client.post(f"{base_url}", json=body)
    data, _ = await assert_status(
        resp,
        status.HTTP_201_CREATED,
    )
    assert ConversationRestGet.model_validate(data)
    second_conversation_id = data["conversationId"]

    assert mocks.notify_via_socket_conversation_created.call_count == 2

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


@pytest.mark.acceptance_test("https://github.com/ITISFoundation/private-issues/issues/51")
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
            (_conversation_service, "notify_via_socket_conversation_created"),
            (_conversation_service, "notify_via_socket_conversation_updated"),
            (_conversation_service, "notify_via_socket_conversation_deleted"),
        ]
    )

    base_url = client.app.router["list_conversations"].url_for()

    # Create a conversation first
    body = {"name": "Support Request - Bug Report", "type": "SUPPORT"}
    resp = await client.post(f"{base_url}", json=body)
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    first_conversation_id = data["conversationId"]

    # Test getting a specific conversation
    get_url = client.app.router["get_conversation"].url_for(conversation_id=first_conversation_id)
    resp = await client.get(f"{get_url}?type=SUPPORT")
    data, _ = await assert_status(resp, expected)
    assert data["conversationId"] == first_conversation_id
    assert data["name"] == "Support Request - Bug Report"

    # Test updating a conversation
    update_url = client.app.router["update_conversation"].url_for(conversation_id=first_conversation_id)
    updated_name = "Updated Support Request - Bug Report"
    resp = await client.patch(
        f"{update_url}?type=SUPPORT",
        json={"name": updated_name},
    )
    data, _ = await assert_status(resp, expected)
    assert data["name"] == updated_name

    assert mocks.notify_via_socket_conversation_updated.call_count == 1

    # Verify the update by getting the conversation again
    resp = await client.get(f"{get_url}?type=SUPPORT")
    data, _ = await assert_status(resp, expected)
    assert data["name"] == updated_name

    # Test deleting a conversation
    delete_url = client.app.router["delete_conversation"].url_for(conversation_id=first_conversation_id)
    resp = await client.delete(f"{delete_url}?type=SUPPORT")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    assert mocks.notify_via_socket_conversation_deleted.call_count == 1

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
        body = {"name": f"Support Request {i + 1}", "type": "SUPPORT"}
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
        get_url = client.app.router["get_conversation"].url_for(conversation_id=conversation_id)
        resp = await client.get(f"{get_url}?type=SUPPORT")
        await assert_status(resp, status.HTTP_404_NOT_FOUND)

        # The new user should not be able to update the conversation
        update_url = client.app.router["update_conversation"].url_for(conversation_id=conversation_id)
        resp = await client.patch(
            f"{update_url}?type=SUPPORT",
            json={"name": "Unauthorized update attempt"},
        )
        await assert_status(resp, status.HTTP_404_NOT_FOUND)

        # The new user should not be able to delete the conversation
        delete_url = client.app.router["delete_conversation"].url_for(conversation_id=conversation_id)
        resp = await client.delete(f"{delete_url}?type=SUPPORT")
        await assert_status(resp, status.HTTP_404_NOT_FOUND)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_conversations_cannot_be_accessed_from_another_product(
    client: TestClient,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    app_products_names: list[ProductName],
):
    """A support conversation belonging to another product must not be reachable
    through the current product's endpoints (cross-product access guard)."""
    assert client.app
    base_url = client.app.router["list_conversations"].url_for()

    # Create a support conversation (belongs to the request's product)
    body = {"name": "User Support Request", "type": "SUPPORT"}
    resp = await client.post(f"{base_url}", json=body)
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    conversation_id = data["conversationId"]

    # Reassign the conversation to a different product directly in the DB
    other_products = [name for name in app_products_names if name != osparc_product_name]
    assert other_products, "Test requires at least one product besides the default"
    other_product = other_products[0]
    async with transaction_context(get_asyncpg_engine(client.app)) as conn:
        await conn.execute(
            conversations.update()
            .where(conversations.c.conversation_id == UUID(conversation_id))
            .values(product_name=other_product)
        )

    # Even the creator can no longer access it through the current product context
    get_url = client.app.router["get_conversation"].url_for(conversation_id=conversation_id)
    resp = await client.get(f"{get_url}?type=SUPPORT")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)

    update_url = client.app.router["update_conversation"].url_for(conversation_id=conversation_id)
    resp = await client.patch(f"{update_url}?type=SUPPORT", json={"name": "Cross-product update attempt"})
    await assert_status(resp, status.HTTP_404_NOT_FOUND)

    delete_url = client.app.router["delete_conversation"].url_for(conversation_id=conversation_id)
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

    get_url = client.app.router["get_conversation"].url_for(conversation_id=fake_conversation_id)
    resp = await client.get(f"{get_url}?type=SUPPORT")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)

    update_url = client.app.router["update_conversation"].url_for(conversation_id=fake_conversation_id)
    resp = await client.patch(
        f"{update_url}?type=SUPPORT",
        json={"name": "Update non-existent"},
    )
    await assert_status(resp, status.HTTP_404_NOT_FOUND)

    delete_url = client.app.router["delete_conversation"].url_for(conversation_id=fake_conversation_id)
    resp = await client.delete(f"{delete_url}?type=SUPPORT")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_conversations_without_type_query_param(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
):
    """Test that endpoints require type query parameter"""

    # Create a conversation via project endpoint first
    project_id = f"{user_project['uuid']}"
    project_conversation_url = client.app.router["create_project_conversation"].url_for(project_id=f"{project_id}")
    body = {"name": "Test Conversation", "type": "PROJECT_STATIC"}
    resp = await client.post(f"{project_conversation_url}", json=body)
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    conversation_id = data["conversationId"]

    # Test list endpoint without type parameter should fail
    list_url = client.app.router["list_conversations"].url_for()
    resp = await client.get(f"{list_url}")
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)

    # All other endpoints should return 400, because we currently support only SUPPORT type
    get_url = client.app.router["get_conversation"].url_for(conversation_id=conversation_id)
    resp = await client.get(f"{get_url}")
    await assert_status(resp, status.HTTP_400_BAD_REQUEST)

    update_url = client.app.router["update_conversation"].url_for(conversation_id=conversation_id)
    resp = await client.patch(f"{update_url}", json={"name": "Updated"})
    await assert_status(resp, status.HTTP_400_BAD_REQUEST)

    delete_url = client.app.router["delete_conversation"].url_for(conversation_id=conversation_id)
    resp = await client.delete(f"{delete_url}")
    await assert_status(resp, status.HTTP_400_BAD_REQUEST)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_conversations_status_filter(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_functions_factory: Callable[[Iterable[tuple[object, str]]], SimpleNamespace],
):
    """Test listing conversations with status filter (ACTIVE/ARCHIVED)"""
    mock_functions_factory(
        [
            (_conversation_service, "notify_via_socket_conversation_created"),
            (_conversation_service, "notify_via_socket_conversation_updated"),
        ]
    )

    assert client.app
    base_url = client.app.router["list_conversations"].url_for()

    # Create two conversations
    for name in ("Conversation A", "Conversation B"):
        body = {"name": name, "type": "SUPPORT"}
        resp = await client.post(f"{base_url}", json=body)
        await assert_status(resp, status.HTTP_201_CREATED)

    # List all - should get 2
    resp = await client.get(f"{base_url}?type=SUPPORT")
    data, _, meta = await assert_status(resp, status.HTTP_200_OK, include_meta=True)
    assert meta["total"] == 2

    # All should be ACTIVE by default
    assert all(c["status"] == "ACTIVE" for c in data)

    # Regular user cannot change status (should get 403)
    conversation_a_id = data[0]["conversationId"]
    update_url = client.app.router["update_conversation"].url_for(conversation_id=conversation_a_id)
    resp = await client.patch(f"{update_url}", json={"status": "ARCHIVED"})
    await assert_status(resp, status.HTTP_403_FORBIDDEN)

    # Filter by ACTIVE - should still get 2 (nothing was archived)
    resp = await client.get(f"{base_url}?type=SUPPORT&status=ACTIVE")
    data, _, meta = await assert_status(resp, status.HTTP_200_OK, include_meta=True)
    assert meta["total"] == 2

    # Filter by ARCHIVED - should get 0
    resp = await client.get(f"{base_url}?type=SUPPORT&status=ARCHIVED")
    data, _, meta = await assert_status(resp, status.HTTP_200_OK, include_meta=True)
    assert meta["total"] == 0


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_conversations_is_read_filters(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_functions_factory: Callable[[Iterable[tuple[object, str]]], SimpleNamespace],
):
    """Test listing conversations with is_read_by_user and is_read_by_support filters"""
    mock_functions_factory(
        [
            (_conversation_service, "notify_via_socket_conversation_created"),
            (_conversation_service, "notify_via_socket_conversation_updated"),
        ]
    )

    assert client.app
    base_url = client.app.router["list_conversations"].url_for()

    # Create a conversation (by default: is_read_by_user=False, is_read_by_support=False)
    body = {"name": "Unread Conversation", "type": "SUPPORT"}
    resp = await client.post(f"{base_url}", json=body)
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    conv_id = data["conversationId"]
    assert data["isReadByUser"] is False
    assert data["isReadBySupport"] is False

    # Filter by is_read_by_user=false - should get 1
    resp = await client.get(f"{base_url}?type=SUPPORT&is_read_by_user=false")
    data, _, meta = await assert_status(resp, status.HTTP_200_OK, include_meta=True)
    assert meta["total"] == 1

    # Filter by is_read_by_user=true - should get 0
    resp = await client.get(f"{base_url}?type=SUPPORT&is_read_by_user=true")
    data, _, meta = await assert_status(resp, status.HTTP_200_OK, include_meta=True)
    assert meta["total"] == 0

    # Mark as read by user
    update_url = client.app.router["update_conversation"].url_for(conversation_id=conv_id)
    resp = await client.patch(f"{update_url}", json={"isReadByUser": True})
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["isReadByUser"] is True

    # Now filter by is_read_by_user=true - should get 1
    resp = await client.get(f"{base_url}?type=SUPPORT&is_read_by_user=true")
    data, _, meta = await assert_status(resp, status.HTTP_200_OK, include_meta=True)
    assert meta["total"] == 1

    # Filter by is_read_by_support=false - should still get 1
    resp = await client.get(f"{base_url}?type=SUPPORT&is_read_by_support=false")
    data, _, meta = await assert_status(resp, status.HTTP_200_OK, include_meta=True)
    assert meta["total"] == 1

    # Filter by is_read_by_support=true - should get 0
    resp = await client.get(f"{base_url}?type=SUPPORT&is_read_by_support=true")
    data, _, meta = await assert_status(resp, status.HTTP_200_OK, include_meta=True)
    assert meta["total"] == 0


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_conversations_status_forbidden_for_regular_user(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_functions_factory: Callable[[Iterable[tuple[object, str]]], SimpleNamespace],
):
    """Test that regular users cannot change conversation status (archive/unarchive)"""
    mock_functions_factory(
        [
            (_conversation_service, "notify_via_socket_conversation_created"),
        ]
    )

    assert client.app
    base_url = client.app.router["list_conversations"].url_for()

    # Create a conversation
    body = {"name": "Support Request", "type": "SUPPORT"}
    resp = await client.post(f"{base_url}", json=body)
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    conversation_id = data["conversationId"]

    # A second user (regular, non-support) should not be able to archive it
    async with LoggedUser(client) as _second_user:
        # Second user cannot even access it (not their conversation)
        update_url = client.app.router["update_conversation"].url_for(conversation_id=conversation_id)
        resp = await client.patch(f"{update_url}", json={"status": "ARCHIVED"})
        await assert_status(resp, status.HTTP_404_NOT_FOUND)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_conversations_archive_by_support_user(
    client: TestClient,
    logged_user: UserInfoDict,
    mocker: MockerFixture,
    mock_functions_factory: Callable[[Iterable[tuple[object, str]]], SimpleNamespace],
):
    """Test that support group members can archive/unarchive conversations and filter by status"""
    mocks = mock_functions_factory(
        [
            (_conversation_service, "notify_via_socket_conversation_created"),
            (_conversation_service, "notify_via_socket_conversation_updated"),
            (_conversation_service, "get_recipients_from_product_support_group"),
        ]
    )
    mocks.get_recipients_from_product_support_group.return_value = set()

    assert client.app
    base_url = client.app.router["list_conversations"].url_for()

    # Create two conversations as regular user
    conversation_ids = []
    for name in ("Conversation A", "Conversation B"):
        body = {"name": name, "type": "SUPPORT"}
        resp = await client.post(f"{base_url}", json=body)
        data, _ = await assert_status(resp, status.HTTP_201_CREATED)
        conversation_ids.append(data["conversationId"])

    # Now mock the user as a support group member
    _support_group_id = 999
    mocked_product = mocker.Mock()
    mocked_product.support_standard_group_id = _support_group_id
    mocked_product.support_chatbot_user_id = None
    mocker.patch.object(_conversation_service.products_service, "get_product", return_value=mocked_product)
    mocker.patch.object(
        _conversation_service,
        "list_user_groups_ids_with_read_access",
        return_value={_support_group_id},
    )

    # Support user can archive a conversation
    update_url = client.app.router["update_conversation"].url_for(conversation_id=conversation_ids[0])
    resp = await client.patch(f"{update_url}", json={"status": "ARCHIVED"})
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["status"] == "ARCHIVED"

    # Verify via GET that the conversation is archived
    get_url = client.app.router["get_conversation"].url_for(conversation_id=conversation_ids[0])
    resp = await client.get(f"{get_url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["status"] == "ARCHIVED"

    # Verify the other conversation is still ACTIVE
    get_url = client.app.router["get_conversation"].url_for(conversation_id=conversation_ids[1])
    resp = await client.get(f"{get_url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["status"] == "ACTIVE"

    # Support user can unarchive
    resp = await client.patch(f"{update_url}", json={"status": "ACTIVE"})
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["status"] == "ACTIVE"


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_conversations_create_with_null_name(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_functions_factory: Callable[[Iterable[tuple[object, str]]], SimpleNamespace],
):
    """Test creating a conversation without a name (omitted or explicitly null)"""
    mock_functions_factory(
        [
            (_conversation_service, "notify_via_socket_conversation_created"),
        ]
    )

    assert client.app
    base_url = client.app.router["list_conversations"].url_for()

    # Create with name omitted
    resp = await client.post(f"{base_url}", json={"type": "SUPPORT"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    assert ConversationRestGet.model_validate(data)
    assert data["name"] is None

    # Create with name explicitly null
    resp = await client.post(f"{base_url}", json={"name": None, "type": "SUPPORT"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    assert ConversationRestGet.model_validate(data)
    assert data["name"] is None


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_conversations_clear_name_via_patch(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_functions_factory: Callable[[Iterable[tuple[object, str]]], SimpleNamespace],
):
    """Test clearing a conversation name by PATCHing with name=null"""
    mock_functions_factory(
        [
            (_conversation_service, "notify_via_socket_conversation_created"),
            (_conversation_service, "notify_via_socket_conversation_updated"),
        ]
    )

    assert client.app
    base_url = client.app.router["list_conversations"].url_for()

    # Create a named conversation
    resp = await client.post(f"{base_url}", json={"name": "My Support Request", "type": "SUPPORT"})
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    conversation_id = data["conversationId"]
    assert data["name"] == "My Support Request"

    # Clear the name via PATCH
    update_url = client.app.router["update_conversation"].url_for(conversation_id=conversation_id)
    resp = await client.patch(f"{update_url}", json={"name": None})
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert ConversationRestGet.model_validate(data)
    assert data["name"] is None

    # Verify the cleared name persists
    get_url = client.app.router["get_conversation"].url_for(conversation_id=conversation_id)
    resp = await client.get(f"{get_url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["name"] is None
