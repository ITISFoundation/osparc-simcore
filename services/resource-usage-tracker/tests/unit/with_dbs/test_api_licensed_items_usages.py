# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments


import sqlalchemy as sa
from servicelib.rabbitmq import RabbitMQRPCClient

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_service_licensed_items_usages(
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    rpc_client: RabbitMQRPCClient,
):
    ...

    # List licensed items usages

    # Get licensed items usages


async def test_rpc_licensed_items_usages_workflow(
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    rpc_client: RabbitMQRPCClient,
):
    ...

    # Can I use the license?

    # Checkout with num of seats

    # Can I use the license?

    # Release num of seats


# Add test for heartbeat check!
