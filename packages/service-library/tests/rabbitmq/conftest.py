# pylint: disable=redefined-outer-name

from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
from typing import Any, cast

import aiodocker
import arrow
import pytest
from faker import Faker
from models_library.rabbitmq_basic_types import RPCNamespace
from pytest_simcore.helpers.rabbitmq_logs import attribute_log_lines
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.xdist import is_xdist_worker
from pytest_simcore.rabbit_service import RabbitWorkerPrincipal
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
) -> AsyncIterator[None]:
    now = arrow.utcnow()
    yield
    if "no_cleanup_check_rabbitmq_server_has_no_errors" in request.keywords:
        return
    if "rabbit_worker_principal" not in request.fixturenames:
        # the test talks to no broker of its own, e.g. the modules here that only test the client
        # logic, so there are no broker logs of this stack to attribute to it
        return
    # looked up here instead of declared as parameters: parameters resolve during setup, which would
    # pull the docker stack fixtures (and their service-selection assertion) into the modules of this
    # directory that deploy no stack. Any test requesting the principal already has it set up.
    container_filters: dict[str, Any] = request.getfixturevalue("stack_rabbit_container_filters")
    principal: RabbitWorkerPrincipal = request.getfixturevalue("rabbit_worker_principal")

    print("--> checking for errors/warnings in rabbitmq logs...")
    shared_broker = is_xdist_worker(request)
    async with aiodocker.Docker() as docker_client:
        containers = await docker_client.containers.list(filters=container_filters)
        assert len(containers) == 1, "missing rabbit container!"

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

    attribution = attribute_log_lines(
        all_logs,
        worker_user=principal.user,
        worker_vhost=principal.vhost,
    )
    if not shared_broker:
        # nothing else talks to this broker, so every line is this test's
        lines_to_check = attribution.mine + attribution.others + attribution.unattributed
    else:
        lines_to_check = list(attribution.mine)
        if "docker_exclusive" in request.keywords:
            # this test held the broker alone, so an unattributable line cannot be another worker's
            lines_to_check.extend(attribution.unattributed)

    warning_logs = [log for log in lines_to_check if "warning" in log]
    error_logs = [log for log in lines_to_check if "error" in log]
    RABBIT_SKIPPED_WARNINGS = [
        "rebuilding indices from scratch",
    ]
    filtered_warning_logs = [log for log in warning_logs if all(w not in log for w in RABBIT_SKIPPED_WARNINGS)]
    assert not filtered_warning_logs, f"warning(s) found in rabbitmq logs for {request.function}"
    assert not error_logs, f"error(s) found in rabbitmq logs for {request.function}"
    print("<-- no error found in rabbitmq server logs")


@pytest.fixture
def random_exchange_name() -> Callable[[], str]:
    def _creator() -> str:
        faker = Faker()  # NOTE: this ensure the faker seed is new each time, since we do not clean the exchanges
        return f"pytest_fake_exchange_{faker.pystr()}"

    return _creator
