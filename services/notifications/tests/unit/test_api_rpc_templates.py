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
    NotificationsTemplatePreviewRpcRequest,
    NotificationsTemplatePreviewRpcResponse,
    NotificationsTemplateRefRpc,
    NotificationsTemplateRpcResponse,
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


async def test_search_templates_no_filters(
    mock_fastapi_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
):
    assert mock_fastapi_app

    rpc_client = await rabbitmq_rpc_client("notifications-test-client")

    templates = await search_templates(rpc_client)
    assert isinstance(templates, list)
    if templates:
        assert isinstance(templates[0], NotificationsTemplateRpcResponse)
        assert templates[0].ref.channel is not None
        assert templates[0].ref.template_name is not None
        assert isinstance(templates[0].context_schema, dict)


async def test_search_templates_by_channel(
    mock_fastapi_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
):
    assert mock_fastapi_app

    rpc_client = await rabbitmq_rpc_client("notifications-test-client")

    templates = await search_templates(rpc_client)
    if templates:
        channel = templates[0].ref.channel
        filtered = await search_templates(rpc_client, channel=channel)
        assert isinstance(filtered, list)
        assert all(t.ref.channel == channel for t in filtered)


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
    request = NotificationsTemplatePreviewRpcRequest(
        ref=template.ref,
        context={
            "subject": "Test Email",
            "body": "This is a test email.",
        }
        | {"product": fake_product_data},
    )

    response = await preview_template(rpc_client, request=request)
    assert isinstance(response, NotificationsTemplatePreviewRpcResponse)
    assert response.ref == template.ref
    assert isinstance(response.content, dict)


async def test_preview_template_not_found(
    mock_fastapi_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
):
    assert mock_fastapi_app

    rpc_client = await rabbitmq_rpc_client("notifications-test-client")

    request = NotificationsTemplatePreviewRpcRequest(
        ref=NotificationsTemplateRefRpc(
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
        request = NotificationsTemplatePreviewRpcRequest(
            ref=template.ref,
            context={"invalid_key": "invalid_value"},  # Invalid context
        )

        with pytest.raises((NotificationsTemplateContextValidationError, RPCServerError)):
            await preview_template(rpc_client, request=request)
