import pytest
from models_library.rpc.notifications.messages import NotificationMessage
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications.messages import (
    send_notification_message,
)
from simcore_service_notifications.clients.celery import EmailChannel

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]


@pytest.mark.usefixtures(
    "mock_celery_app",
    "mock_celery_worker",
    "fastapi_app",
)
async def test_send_email(
    notifications_rabbitmq_rpc_client: RabbitMQRPCClient,
):
    await send_notification_message(
        notifications_rabbitmq_rpc_client,
        message=NotificationMessage(
            event_type="on_account_requested",
            channel=EmailChannel(to="test@example.com"),
            context={"key": "value"},
        ),
    )
