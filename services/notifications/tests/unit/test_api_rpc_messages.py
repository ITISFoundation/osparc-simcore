# pylint: disable=unused-argument
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from models_library.notifications import ChannelType
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications._template import (
    search_templates,
)

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
    "redis",
]


async def test_send_message_from_templates(
    mock_fastapi_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
):
    assert mock_fastapi_app

    rpc_client = await rabbitmq_rpc_client("notifications-test-client")

    all_templates = await search_templates(rpc_client, channel=None, template_name=None)
    if all_templates:
        channel = ChannelType.email
        filtered = await search_templates(rpc_client, channel=channel, template_name=None)
        # Check that all returned templates match the filter
        assert all(t.ref.channel == channel for t in filtered)
        # Check that filtered is a subset of all_templates
        assert all(template in all_templates for template in filtered)
