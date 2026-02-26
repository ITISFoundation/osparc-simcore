# pylint: disable=unused-argument
from fastapi import FastAPI
from models_library.notifications.rpc._message import SendMessageFromTemplateRequest
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications import (
    send_message_from_template,
)

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
    "redis",
]


async def test_send_message_from_templates(
    mock_fastapi_app: FastAPI,
    notifications_rpc_client: RabbitMQRPCClient,
):
    assert mock_fastapi_app

    await send_message_from_template(
        notifications_rpc_client,
        request=SendMessageFromTemplateRequest(),
    )
