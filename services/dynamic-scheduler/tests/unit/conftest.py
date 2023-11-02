from collections.abc import Awaitable, Callable

import pytest
from faker import Faker
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQRPCClient


@pytest.fixture
def is_pdb_enabled(request: pytest.FixtureRequest):
    """Returns true if tests are set to use interactive debugger, i.e. --pdb"""
    options = request.config.option
    return options.usepdb


#
# rabbit-MQ
#


@pytest.fixture
def disable_rabbitmq_and_rpc_setup(mocker: MockerFixture) -> Callable:
    def _do():
        # The following services are affected if rabbitmq is not in place
        mocker.patch(
            "simcore_service_dynamic_scheduler.core.application.setup_rabbitmq"
        )
        mocker.patch(
            "simcore_service_dynamic_scheduler.core.application.setup_rpc_api_routes"
        )

    return _do


@pytest.fixture
def with_disabled_rabbitmq_and_rpc(disable_rabbitmq_and_rpc_setup: Callable):
    disable_rabbitmq_and_rpc_setup()


@pytest.fixture
async def rpc_client(
    faker: Faker, rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]]
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client(f"web-server-client-{faker.word()}")
