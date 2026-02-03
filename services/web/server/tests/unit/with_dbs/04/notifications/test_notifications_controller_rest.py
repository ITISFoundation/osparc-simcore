# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from http import HTTPStatus
from typing import Any

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserStatus
from faker import Faker
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from models_library.api_schemas_webserver.notifications import (
    NotificationsTemplateGet,
    NotificationsTemplatePreviewGet,
)
from models_library.notifications import ChannelType
from models_library.rpc.notifications.template import (
    NotificationsTemplatePreviewRpcResponse,
    NotificationsTemplateRefRpc,
    NotificationsTemplateRpcResponse,
)
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.notifications._controller import _rest

pytest_simcore_core_services_selection = []


@pytest.fixture
def fake_template_preview_response(faker: Faker) -> NotificationsTemplatePreviewRpcResponse:
    """Create a fake template preview response"""
    return NotificationsTemplatePreviewRpcResponse(
        ref=NotificationsTemplateRefRpc(
            channel=ChannelType.email,
            template_name="test_template",
        ),
        content={
            "subject": faker.sentence(),
            "bodyHtml": faker.text(),
            "bodyText": faker.text(),
        },
    )


@pytest.fixture
def fake_template_response(faker: Faker) -> NotificationsTemplateRpcResponse:
    """Create a fake template response"""
    return NotificationsTemplateRpcResponse(
        ref=NotificationsTemplateRefRpc(
            channel=ChannelType.email,
            template_name="test_template",
        ),
        context_schema={
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["subject", "body"],
        },
    )


@pytest.fixture
def fake_email_content() -> dict[str, Any]:
    """Create standard email content object"""
    return {
        "subject": "Test",
        "bodyHtml": "<p>Test Body</p>",
        "bodyText": "Test Body",
    }


@pytest.mark.parametrize(
    "user_role,expected_status",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_403_FORBIDDEN),
        (UserRole.TESTER, status.HTTP_403_FORBIDDEN),
        (UserRole.PRODUCT_OWNER, status.HTTP_202_ACCEPTED),
        (UserRole.ADMIN, status.HTTP_202_ACCEPTED),
    ],
)
async def test_send_message_access_control(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected_status: HTTPStatus,
    mocked_notifications_rpc_client: MockerFixture,
    fake_email_content: dict[str, Any],
    create_test_users: Callable[[int, list | None], AbstractAsyncContextManager[list[UserInfoDict]]],
):
    """Test access control for send_message endpoint"""
    assert client.app
    url = client.app.router["send_message"].url_for()

    async with create_test_users(1, None) as users:
        # Prepare request body
        body = {
            "channel": "email",
            "recipients": [users[0]["primary_gid"]],
            "content": fake_email_content,
        }

        response = await client.post(url.path, json=body)
        await assert_status(response, expected_status)


@pytest.mark.parametrize(
    "user_role,expected_status",
    [
        (UserRole.PRODUCT_OWNER, status.HTTP_400_BAD_REQUEST),
        (UserRole.ADMIN, status.HTTP_400_BAD_REQUEST),
    ],
)
async def test_send_message_no_active_recipients(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected_status: HTTPStatus,
    mocked_notifications_rpc_client: MockerFixture,
    fake_email_content: dict[str, Any],
    create_test_users: Callable[[int, list | None], AbstractAsyncContextManager[list[UserInfoDict]]],
):
    """Test that send_message returns 400 when no active recipients are provided"""
    assert client.app
    url = client.app.router["send_message"].url_for()

    async with create_test_users(3, [UserStatus.ACTIVE, UserStatus.BANNED, UserStatus.EXPIRED]) as (_, user2, user3):
        # Prepare request body
        body = {
            "channel": "email",
            "recipients": [user2["primary_gid"], user3["primary_gid"]],
            "content": fake_email_content,
        }

        response = await client.post(url.path, json=body)
        await assert_status(response, expected_status)


@pytest.mark.parametrize("user_role", [UserRole.PRODUCT_OWNER, UserRole.ADMIN])
async def test_send_message_returns_task(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_notifications_rpc_client: MockerFixture,
    fake_email_content: dict[str, Any],
    create_test_users: Callable[[int, list | None], AbstractAsyncContextManager[list[UserInfoDict]]],
):
    """Test that send_message returns a task resource"""
    assert client.app
    url = client.app.router["send_message"].url_for()

    async with create_test_users(1, None) as users:
        # Prepare request body
        body = {
            "channel": "email",
            "recipients": [users[0]["primary_gid"]],
            "content": fake_email_content,
        }

        response = await client.post(url.path, json=body)
        data, error = await assert_status(response, status.HTTP_202_ACCEPTED)
        assert not error

        # Validate response structure
        task = TaskGet.model_validate(data)

        # Validate that hrefs are properly formed
        assert f"{task.task_id}" in task.status_href
        assert f"{task.task_id}" in task.abort_href

        assert task.result_href is not None
        assert f"{task.task_id}" in task.result_href


@pytest.mark.parametrize("user_role", [UserRole.PRODUCT_OWNER, UserRole.ADMIN])
@pytest.mark.parametrize(
    "recipients_count,expected_status",
    [
        # Single recipient
        (1, status.HTTP_202_ACCEPTED),
        # Multiple recipients
        (2, status.HTTP_202_ACCEPTED),
    ],
)
async def test_send_message_with_different_inputs(
    client: TestClient,
    logged_user: UserInfoDict,
    recipients_count: int,
    expected_status: HTTPStatus,
    mocked_notifications_rpc_client: MockerFixture,
    fake_email_content: dict[str, Any],
    create_test_users: Callable[[int, list | None], AbstractAsyncContextManager[list[UserInfoDict]]],
):
    """Test send_message with various valid inputs"""
    assert client.app
    url = client.app.router["send_message"].url_for()

    async with create_test_users(recipients_count, None) as users:
        recipients = [user["primary_gid"] for user in users]

        body = {
            "channel": "email",
            "recipients": recipients,
            "content": fake_email_content,
        }

        response = await client.post(url.path, json=body)
        data, error = await assert_status(response, expected_status)

        if expected_status == status.HTTP_202_ACCEPTED:
            assert not error
            task = TaskGet.model_validate(data)
            assert task.task_id


@pytest.mark.parametrize(
    "user_role,expected_status",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_403_FORBIDDEN),
        (UserRole.TESTER, status.HTTP_403_FORBIDDEN),
        (UserRole.PRODUCT_OWNER, status.HTTP_200_OK),
        (UserRole.ADMIN, status.HTTP_200_OK),
    ],
)
async def test_preview_template_access_control(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected_status: HTTPStatus,
    mocked_notifications_rpc_client: MockerFixture,
    fake_template_preview_response: NotificationsTemplatePreviewRpcResponse,
):
    """Test access control for preview_template endpoint"""
    assert client.app

    # Mock the RPC call
    mocked_notifications_rpc_client.patch(
        f"{_rest.__name__}.remote_preview_template",
        return_value=fake_template_preview_response,
    )

    url = client.app.router["preview_template"].url_for()

    body = {
        "ref": {
            "channel": "email",
            "template_name": "empty",
        },
        "context": {
            "subject": "Test",
            "body": "Body",
        },
    }

    response = await client.post(url.path, json=body)
    await assert_status(response, expected_status)


@pytest.mark.parametrize("user_role", [UserRole.PRODUCT_OWNER, UserRole.ADMIN])
async def test_preview_template_success(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_notifications_rpc_client: MockerFixture,
    fake_template_preview_response: NotificationsTemplatePreviewRpcResponse,
    fake_email_content: dict[str, Any],
):
    """Test successful template preview"""
    assert client.app

    # Mock the RPC call
    mocked_notifications_rpc_client.patch(
        f"{_rest.__name__}.remote_preview_template",
        return_value=fake_template_preview_response,
    )

    url = client.app.router["preview_template"].url_for()

    body = {
        "ref": {
            "channel": "email",
            "template_name": "test_template",
        },
        "context": fake_email_content,
    }

    response = await client.post(url.path, json=body)
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert not error

    # Validate response structure
    preview = NotificationsTemplatePreviewGet.model_validate(data)
    assert preview.ref.channel == ChannelType.email
    assert preview.ref.template_name == "test_template"
    assert preview.content


@pytest.mark.parametrize("user_role", [UserRole.PRODUCT_OWNER, UserRole.ADMIN])
async def test_preview_template_enriches_context_with_product_data(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_notifications_rpc_client: MockerFixture,
    mocker: MockerFixture,
    fake_email_content: dict[str, Any],
):
    """Test that preview_template enriches context with product data"""
    assert client.app

    # Spy on the RPC call to verify the enriched context
    mock_rpc_call = mocker.patch(
        f"{_rest.__name__}.remote_preview_template",
        return_value=NotificationsTemplatePreviewRpcResponse(
            ref=NotificationsTemplateRefRpc(
                channel=ChannelType.email,
                template_name="test",
            ),
            content={"subject": "Test", "bodyHtml": "<p>Test Body</p>", "bodyText": "Test Body"},
        ),
    )

    url = client.app.router["preview_template"].url_for()

    body = {
        "ref": {
            "channel": "email",
            "template_name": "test_template",
        },
        "context": fake_email_content,
    }

    response = await client.post(url.path, json=body)
    await assert_status(response, status.HTTP_200_OK)

    # Verify RPC was called with enriched context including product data
    assert mock_rpc_call.called
    call_args = mock_rpc_call.call_args
    assert "request" in call_args.kwargs
    request = call_args.kwargs["request"]
    assert "product" in request.context


@pytest.mark.parametrize(
    "user_role,expected_status",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_403_FORBIDDEN),
        (UserRole.TESTER, status.HTTP_403_FORBIDDEN),
        (UserRole.PRODUCT_OWNER, status.HTTP_200_OK),
        (UserRole.ADMIN, status.HTTP_200_OK),
    ],
)
async def test_search_templates_access_control(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected_status: HTTPStatus,
    mocked_notifications_rpc_client: MockerFixture,
    fake_template_response: NotificationsTemplateRpcResponse,
):
    """Test access control for search_templates endpoint"""
    assert client.app

    # Mock the RPC call
    mocked_notifications_rpc_client.patch(
        f"{_rest.__name__}.remote_search_templates",
        return_value=[fake_template_response],
    )

    url = client.app.router["search_templates"].url_for()

    response = await client.get(url.path)
    await assert_status(response, expected_status)


@pytest.mark.parametrize("user_role", [UserRole.PRODUCT_OWNER, UserRole.ADMIN])
async def test_search_templates_no_filters(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_notifications_rpc_client: MockerFixture,
    fake_template_response: NotificationsTemplateRpcResponse,
):
    """Test searching templates without filters"""
    assert client.app

    # Mock the RPC call
    mocked_notifications_rpc_client.patch(
        f"{_rest.__name__}.remote_search_templates",
        return_value=[fake_template_response],
    )

    url = client.app.router["search_templates"].url_for()

    response = await client.get(url.path)
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert not error

    # Validate response structure
    templates = TypeAdapter(list[NotificationsTemplateGet]).validate_python(data)
    assert len(templates) == 1
    assert templates[0].ref.channel == ChannelType.email
    assert templates[0].ref.template_name == "test_template"
    assert templates[0].context_schema


@pytest.mark.parametrize("user_role", [UserRole.PRODUCT_OWNER, UserRole.ADMIN])
@pytest.mark.parametrize(
    "query_params,expected_status",
    [
        # Filter by channel only
        ({"channel": "email"}, status.HTTP_200_OK),
        # Filter by template_name only
        ({"template_name": "welcome"}, status.HTTP_200_OK),
        # Filter by both
        ({"channel": "email", "template_name": "welcome"}, status.HTTP_200_OK),
        # No filters
        ({}, status.HTTP_200_OK),
    ],
)
async def test_search_templates_with_filters(
    client: TestClient,
    logged_user: UserInfoDict,
    query_params: dict[str, str],
    expected_status: HTTPStatus,
    mocked_notifications_rpc_client: MockerFixture,
    fake_template_response: NotificationsTemplateRpcResponse,
    mocker: MockerFixture,
):
    """Test searching templates with different filter combinations"""
    assert client.app

    # Mock the RPC call and spy on it
    mock_rpc = mocker.patch(
        f"{_rest.__name__}.remote_search_templates",
        return_value=[fake_template_response],
    )

    url = client.app.router["search_templates"].url_for()

    response = await client.get(url.path, params=query_params)
    _, error = await assert_status(response, expected_status)
    assert not error

    # Verify RPC was called with correct parameters
    assert mock_rpc.called
    call_kwargs = mock_rpc.call_args.kwargs
    if "channel" in query_params:
        assert call_kwargs["channel"] == query_params["channel"]
    if "template_name" in query_params:
        assert call_kwargs["template_name"] == query_params["template_name"]


@pytest.mark.parametrize("user_role", [UserRole.PRODUCT_OWNER, UserRole.ADMIN])
async def test_search_templates_empty_result(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_notifications_rpc_client: MockerFixture,
    mocker: MockerFixture,
):
    """Test searching templates when no templates match"""
    assert client.app

    mocker.patch(
        f"{_rest.__name__}.remote_search_templates",
        return_value=[],
    )

    url = client.app.router["search_templates"].url_for()

    response = await client.get(url.path)
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert not error

    # Validate response is empty list
    templates = TypeAdapter(list[NotificationsTemplateGet]).validate_python(data)
    assert len(templates) == 0
