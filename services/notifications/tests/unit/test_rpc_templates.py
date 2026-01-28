from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from models_library.rpc.notifications.template import NotificationsTemplateRpcResponse
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications.notifications_templates import (
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

    # Get all templates first
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
