from celery.contrib.testing.worker import TestWorkController
from servicelib.rabbitmq import RabbitMQRPCClient


async def test_send_email(
    notifications_rabbitmq_rpc_client: RabbitMQRPCClient,
    with_celery_worker: TestWorkController,
):
    pass
