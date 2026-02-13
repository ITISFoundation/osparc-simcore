# pylint: disable=unused-argument
from collections.abc import Awaitable, Callable

import pytest
from fastapi import FastAPI
from models_library.notifications import ChannelType
from models_library.notifications_errors import (
    NotificationsTemplateContextValidationError,
    NotificationsTemplateNotFoundError,
)
from models_library.rpc.notifications.template import (
    TemplatePreviewRpcRequest,
    TemplatePreviewRpcResponse,
    TemplateRefRpc,
)
from servicelib.rabbitmq import RabbitMQRPCClient, RPCServerError
from servicelib.rabbitmq.rpc_interfaces.notifications.notifications_templates import (
    preview_template,
    search_templates,
)

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
    "redis",
]


async def test_search_templates_by_channel(
    mock_fastapi_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
):
    assert mock_fastapi_app

    rpc_client = await rabbitmq_rpc_client("notifications-test-client")

    all_templates = await search_templates(rpc_client)
    if all_templates:
        channel = ChannelType.email
        filtered = await search_templates(rpc_client, channel=channel)
        # Check that all returned templates match the filter
        assert all(t.ref.channel == channel for t in filtered)
        # Check that filtered is a subset of all_templates
        assert all(template in all_templates for template in filtered)


async def test_search_templates_by_ref(
    mock_fastapi_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
):
    assert mock_fastapi_app

    rpc_client = await rabbitmq_rpc_client("notifications-test-client")

    all_templates = await search_templates(rpc_client)
    if all_templates:
        channel = ChannelType.email
        template_name = "empty"
        filtered = await search_templates(rpc_client, channel=channel, template_name=template_name)
        assert len(filtered) == 1

        # Check that returned template match the filter
        assert filtered[0].ref.channel == channel
        assert filtered[0].ref.template_name == template_name


async def test_search_templates_non_existent(
    mock_fastapi_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
):
    assert mock_fastapi_app

    rpc_client = await rabbitmq_rpc_client("notifications-test-client")

    filtered = await search_templates(rpc_client, template_name="non_existent_template")
    assert filtered == []


async def test_preview_template_success(
    mock_fastapi_app: FastAPI,
    fake_product_data: dict[str, str],
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
):
    assert mock_fastapi_app

    rpc_client = await rabbitmq_rpc_client("notifications-test-client")

    templates = await search_templates(rpc_client, channel=ChannelType.email, template_name="empty")
    assert len(templates) == 1

    template = templates[0]
    request = TemplatePreviewRpcRequest(
        ref=template.ref,
        context={
            "subject": "Test Email",
            "body": "This is a test email.",
        }
        | {"product": fake_product_data},
    )

    response = await preview_template(rpc_client, request=request)
    assert isinstance(response, TemplatePreviewRpcResponse)
    assert response.ref == template.ref
    assert isinstance(response.message_content, dict)


async def test_preview_template_not_found(
    mock_fastapi_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
):
    assert mock_fastapi_app

    rpc_client = await rabbitmq_rpc_client("notifications-test-client")

    request = TemplatePreviewRpcRequest(
        ref=TemplateRefRpc(
            channel=ChannelType.email,
            template_name="non_existent_template",
        ),
        context={},
    )

    with pytest.raises(NotificationsTemplateNotFoundError):
        await preview_template(rpc_client, request=request)


async def test_preview_template_invalid_context(
    mock_fastapi_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
):
    assert mock_fastapi_app

    rpc_client = await rabbitmq_rpc_client("notifications-test-client")

    # Get available templates first
    templates = await search_templates(rpc_client)
    if templates:
        template = templates[0]
        request = TemplatePreviewRpcRequest(
            ref=template.ref,
            context={"invalid_key": "invalid_value"},  # Invalid context
        )

        with pytest.raises((NotificationsTemplateContextValidationError, RPCServerError)):
            await preview_template(rpc_client, request=request)
