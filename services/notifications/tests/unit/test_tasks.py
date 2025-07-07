from celery.contrib.testing.worker import TestWorkController
from fastapi import FastAPI
from models_library.rpc.notifications.messages import NotificationMessage
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications.messages import (
    send_notification_message,
)
from simcore_service_notifications.clients.celery import EmailRecipient

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]


async def test_send_email(
    initialized_app: FastAPI,
    notifications_rabbitmq_rpc_client: RabbitMQRPCClient,
    with_celery_worker: TestWorkController,
):
    await send_notification_message(
        notifications_rabbitmq_rpc_client,
        message=NotificationMessage(
            event="test_event",
            context={"key": "value"},
        ),
        recipients=[EmailRecipient(address="test@example.com")],
    )
