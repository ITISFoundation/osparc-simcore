from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
from typing import Any, cast

import aiodocker
import arrow
import pytest
from faker import Faker
from models_library.rabbitmq_basic_types import RPCNamespace
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.xdist import get_max_xdist_workers, is_xdist_worker
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient


@pytest.fixture
async def rpc_client(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("pytest_rpc_client")


@pytest.fixture
def namespace() -> RPCNamespace:
    return RPCNamespace.from_entries({f"test{i}": f"test{i}" for i in range(8)})


@pytest.fixture
def stack_rabbit_container_filters(env_vars_for_docker_compose: EnvVarsDict) -> dict[str, Any]:
    """aiodocker filters selecting the `rabbit` container of this run's stack only

    A name-only filter also matches the rabbits of other checkouts sharing the daemon.
    """
    stack_name = env_vars_for_docker_compose["SWARM_STACK_NAME"]
    return {
        "name": ["rabbit"],
        "label": [f"com.docker.stack.namespace={stack_name}"],
    }


@pytest.fixture(autouse=True)
async def cleanup_check_rabbitmq_server_has_no_errors(
    request: pytest.FixtureRequest,
    stack_rabbit_container_filters: dict[str, Any],
) -> AsyncIterator[None]:
    now = arrow.utcnow()
    yield
    if "no_cleanup_check_rabbitmq_server_has_no_errors" in request.keywords:
        return
    print("--> checking for errors/warnings in rabbitmq logs...")
    shared_broker = is_xdist_worker(request) and get_max_xdist_workers(request.config) > 1
    async with aiodocker.Docker() as docker_client:
        containers = await docker_client.containers.list(filters=stack_rabbit_container_filters)
        assert len(containers) == 1, "missing rabbit container!"

        if shared_broker:
            print("--> skipped the rabbitmq log check: the broker is shared with the other workers")
            return

        rabbit_container = containers[0]
        all_logs = await cast(
            Coroutine,
            rabbit_container.log(
                stdout=True,
                stderr=True,
                follow=False,
                since=now.timestamp(),
            ),
        )

    warning_logs = [log for log in all_logs if "warning" in log]
    error_logs = [log for log in all_logs if "error" in log]
    RABBIT_SKIPPED_WARNINGS = [
        "rebuilding indices from scratch",
    ]
    filtered_warning_logs = [log for log in warning_logs if all(w not in log for w in RABBIT_SKIPPED_WARNINGS)]
    assert not filtered_warning_logs, f"warning(s) found in rabbitmq logs for {request.function}"
    assert not error_logs, f"error(s) found in rabbitmq logs for {request.function}"
    print("<-- no error founds in rabbitmq server logs, that's great. good job!")


@pytest.fixture
def random_exchange_name() -> Callable[[], str]:
    def _creator() -> str:
        faker = Faker()  # NOTE: this ensure the faker seed is new each time, since we do not clean the exchanges
        return f"pytest_fake_exchange_{faker.pystr()}"

    return _creator
