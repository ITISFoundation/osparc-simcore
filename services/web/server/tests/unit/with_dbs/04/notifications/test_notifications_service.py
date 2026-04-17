# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserStatus
from faker import Faker
from models_library.notifications import Channel
from models_library.notifications.errors import (
    NotificationsNoActiveRecipientsError,
    NotificationsUnsupportedChannelError,
)
from models_library.notifications.rpc import SendMessageResponse
from pytest_mock import MockerFixture
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.notifications import _service
from simcore_service_webserver.notifications.models import EmailContact
from simcore_service_webserver.notifications.notifications_service import (
    send_message_from_template,
)

pytest_simcore_core_services_selection = []


@pytest.fixture(params=[UserRole.USER])
def user_role(request: pytest.FixtureRequest) -> UserRole:
    return request.param


@pytest.fixture
def mocked_send_message_from_template_rpc(
    mocker: MockerFixture,
) -> SendMessageResponse:
    fake_response = SendMessageResponse(
        task_or_group_uuid=uuid.uuid4(),
        task_name="send_message_from_template",
    )
    mocker.patch(
        f"{_service.__name__}.remote_send_message_from_template",
        autospec=True,
        return_value=fake_response,
    )
    return fake_response


@pytest.fixture
def fake_template_context(faker: Faker) -> dict[str, Any]:
    return {
        "user": {
            "first_name": faker.first_name(),
            "user_name": faker.user_name(),
        },
        "host": faker.domain_name(),
        "success": True,
        "link": faker.url(),
        "reason": None,
    }


async def test_send_message_from_template_with_external_contacts(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_notifications_rpc_client: MockerFixture,
    mocked_send_message_from_template_rpc: SendMessageResponse,
    fake_template_context: dict[str, Any],
    faker: Faker,
):
    """Test send_message_from_template with external contacts (no group_ids)"""
    assert client.app

    external_contacts = [
        EmailContact(name=faker.name(), email=faker.email()),
    ]

    task_uuid, task_name = await send_message_from_template(
        client.app,
        user_id=logged_user["id"],
        product_name="osparc",
        channel=Channel.email,
        group_ids=None,
        external_contacts=external_contacts,
        template_name="reset_password",
        context=fake_template_context,
    )

    assert task_uuid == mocked_send_message_from_template_rpc.task_or_group_uuid
    assert task_name == mocked_send_message_from_template_rpc.task_name


async def test_send_message_from_template_with_group_ids(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_notifications_rpc_client: MockerFixture,
    mocked_send_message_from_template_rpc: SendMessageResponse,
    fake_template_context: dict[str, Any],
    create_test_users: Callable[..., AbstractAsyncContextManager[list[UserInfoDict]]],
):
    """Test send_message_from_template with group_ids"""
    assert client.app

    async with create_test_users(2, None) as users:
        group_ids = [int(user["primary_gid"]) for user in users]

        task_uuid, task_name = await send_message_from_template(
            client.app,
            user_id=logged_user["id"],
            product_name="osparc",
            channel=Channel.email,
            group_ids=group_ids,
            external_contacts=None,
            template_name="reset_password",
            context=fake_template_context,
        )

        assert task_uuid == mocked_send_message_from_template_rpc.task_or_group_uuid
        assert task_name == mocked_send_message_from_template_rpc.task_name


async def test_send_message_from_template_enriches_context_with_product_data(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_notifications_rpc_client: MockerFixture,
    fake_template_context: dict[str, Any],
    mocker: MockerFixture,
    faker: Faker,
):
    """Test that the context is enriched with product data before calling RPC"""
    assert client.app

    mock_rpc = mocker.patch(
        f"{_service.__name__}.remote_send_message_from_template",
        autospec=True,
        return_value=SendMessageResponse(
            task_or_group_uuid=uuid.uuid4(),
            task_name="send_message_from_template",
        ),
    )

    external_contacts = [
        EmailContact(name=faker.name(), email=faker.email()),
    ]

    await send_message_from_template(
        client.app,
        user_id=logged_user["id"],
        product_name="osparc",
        channel=Channel.email,
        group_ids=None,
        external_contacts=external_contacts,
        template_name="reset_password",
        context=fake_template_context,
    )

    assert mock_rpc.called
    call_kwargs = mock_rpc.call_args.kwargs
    assert "context" in call_kwargs
    context = call_kwargs["context"]
    assert "product" in context
    # Original context keys should still be present
    for key in fake_template_context:
        assert key in context


async def test_send_message_from_template_passes_correct_template_ref(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_notifications_rpc_client: MockerFixture,
    fake_template_context: dict[str, Any],
    mocker: MockerFixture,
    faker: Faker,
):
    """Test that the correct template_ref and addressing are passed to the RPC"""
    assert client.app

    mock_rpc = mocker.patch(
        f"{_service.__name__}.remote_send_message_from_template",
        autospec=True,
        return_value=SendMessageResponse(
            task_or_group_uuid=uuid.uuid4(),
            task_name="send_message_from_template",
        ),
    )

    external_contacts = [
        EmailContact(name=faker.name(), email=faker.email()),
    ]

    await send_message_from_template(
        client.app,
        user_id=logged_user["id"],
        product_name="osparc",
        channel=Channel.email,
        group_ids=None,
        external_contacts=external_contacts,
        template_name="reset_password",
        context=fake_template_context,
    )

    assert mock_rpc.called
    call_kwargs = mock_rpc.call_args.kwargs

    # Verify template_ref
    template_ref = call_kwargs["template_ref"]
    assert template_ref.channel == Channel.email
    assert template_ref.template_name == "reset_password"

    # Verify addressing has from and to
    addressing = call_kwargs["addressing"]
    assert addressing.from_ is not None
    assert len(addressing.to) == 1
    assert addressing.to[0].email == external_contacts[0].email

    # Verify owner params
    assert call_kwargs["owner"] is not None
    assert call_kwargs["user_id"] == logged_user["id"]
    assert call_kwargs["product_name"] == "osparc"


async def test_send_message_from_template_unsupported_channel(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_notifications_rpc_client: MockerFixture,
    mocked_send_message_from_template_rpc: SendMessageResponse,
    fake_template_context: dict[str, Any],
    faker: Faker,
):
    """Test that unsupported channels raise NotificationsUnsupportedChannelError"""
    assert client.app

    external_contacts = [
        EmailContact(name=faker.name(), email=faker.email()),
    ]

    # Simulate a hypothetical unsupported channel value
    unsupported_channel = "pigeon"

    with pytest.raises(NotificationsUnsupportedChannelError):
        await send_message_from_template(
            client.app,
            user_id=logged_user["id"],
            product_name="osparc",
            channel=unsupported_channel,  # type: ignore[arg-type]
            group_ids=None,
            external_contacts=external_contacts,
            template_name="reset_password",
            context=fake_template_context,
        )


async def test_send_message_from_template_no_active_recipients(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_notifications_rpc_client: MockerFixture,
    mocked_send_message_from_template_rpc: SendMessageResponse,
    fake_template_context: dict[str, Any],
    create_test_users: Callable[..., AbstractAsyncContextManager[list[UserInfoDict]]],
):
    """Test that send_message_from_template raises when no active recipients found"""
    assert client.app

    async with create_test_users(2, [UserStatus.BANNED, UserStatus.EXPIRED]) as users:
        group_ids = [int(user["primary_gid"]) for user in users]

        with pytest.raises(NotificationsNoActiveRecipientsError):
            await send_message_from_template(
                client.app,
                user_id=logged_user["id"],
                product_name="osparc",
                channel=Channel.email,
                group_ids=group_ids,
                external_contacts=None,
                template_name="reset_password",
                context=fake_template_context,
            )


async def test_send_message_from_template_with_both_groups_and_external_contacts(
    client: TestClient,
    logged_user: UserInfoDict,
    mocked_notifications_rpc_client: MockerFixture,
    fake_template_context: dict[str, Any],
    create_test_users: Callable[..., AbstractAsyncContextManager[list[UserInfoDict]]],
    mocker: MockerFixture,
    faker: Faker,
):
    """Test send_message_from_template with both group_ids and external_contacts"""
    assert client.app

    mock_rpc = mocker.patch(
        f"{_service.__name__}.remote_send_message_from_template",
        autospec=True,
        return_value=SendMessageResponse(
            task_or_group_uuid=uuid.uuid4(),
            task_name="send_message_from_template",
        ),
    )

    external_contacts = [
        EmailContact(name=faker.name(), email=faker.email()),
    ]

    async with create_test_users(1, None) as users:
        group_ids = [int(users[0]["primary_gid"])]

        await send_message_from_template(
            client.app,
            user_id=logged_user["id"],
            product_name="osparc",
            channel=Channel.email,
            group_ids=group_ids,
            external_contacts=external_contacts,
            template_name="reset_password",
            context=fake_template_context,
        )

        assert mock_rpc.called
        call_kwargs = mock_rpc.call_args.kwargs
        addressing = call_kwargs["addressing"]
        # Should have both group users and external contacts
        assert len(addressing.to) >= 2
