# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access

import asyncio
import contextlib
import json
import logging
import urllib.error
import urllib.request
from base64 import b64encode
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Annotated, Any, Final
from urllib.parse import quote

import aio_pika
import pytest
import tenacity
from annotated_types import doc
from servicelib.rabbitmq import QueueName, RabbitMQClient, RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings
from tenacity import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception, retry_if_exception_type
from tenacity.stop import stop_after_attempt, stop_after_delay
from tenacity.wait import wait_fixed, wait_random_exponential

from .helpers.docker import get_service_published_port
from .helpers.host import get_localhost_ip
from .helpers.logging_tools import log_context
from .helpers.typing_env import EnvVarsDict
from .helpers.xdist import get_worker_id, is_xdist_worker

_logger = logging.getLogger(__name__)

_MGMT_API_TIMEOUT_S: Final[Annotated[int, doc("per-request timeout of the RabbitMQ management API")]] = 10
_MGMT_API_RETRY_MAX_WAIT_S: Final[
    Annotated[int, doc("cap of the jittered exponential backoff between management-API retries")]
] = 10
_MGMT_API_RETRY_TIMEOUT_S: Final[
    Annotated[int, doc("time budget to ride out a transient broker stall before failing")]
] = 120


def _get_management_port(stack_name: str) -> int:
    # NOTE: no fallback port here: if the published management port cannot be resolved the
    # stack is broken and the run would fail confusingly later on, so fail loudly right here
    published = get_service_published_port("rabbit", target_ports=15672, stack_name=stack_name)
    assert published.isdigit(), (
        f"RabbitMQ management API port is not published (got '{published}'): the deployed "
        "'rabbit' service must publish 15672 (see services/docker-compose.yml) — the per-worker "
        "vhost isolation cannot work without it"
    )
    return int(published)


def _get_management_url(stack_name: str) -> str:
    """Base URL of the RabbitMQ management API of the stack's `rabbit` service"""
    return f"http://{get_localhost_ip()}:{_get_management_port(stack_name)}"


@tenacity.retry(
    wait=wait_fixed(5),
    stop=stop_after_attempt(60),
    before_sleep=before_sleep_log(_logger, logging.INFO),
    reraise=True,
)
async def wait_till_rabbit_responsive(url: str) -> None:
    async with await aio_pika.connect(url):
        ...


def _is_transient_network_error(exc: BaseException) -> bool:
    """Any connection-level OSError is transient: an HTTPError means the broker answered"""
    return isinstance(exc, OSError) and not isinstance(exc, urllib.error.HTTPError)


@tenacity.retry(
    retry=retry_if_exception(_is_transient_network_error),
    wait=wait_random_exponential(max=_MGMT_API_RETRY_MAX_WAIT_S),
    stop=stop_after_delay(_MGMT_API_RETRY_TIMEOUT_S),
    before_sleep=before_sleep_log(_logger, logging.INFO),
    reraise=True,
)
def _management_api_request(method: str, url: str, user: str, password: str, body: dict | None = None) -> None:
    """Retries transient connection errors: the broker can stall briefly under concurrent xdist load."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)  # noqa: S310
    request.add_header("Content-Type", "application/json")
    credentials = b64encode(f"{user}:{password}".encode()).decode()
    request.add_header("Authorization", f"Basic {credentials}")
    try:
        urllib.request.urlopen(request, timeout=_MGMT_API_TIMEOUT_S)  # noqa: S310
    except urllib.error.HTTPError as exc:
        if exc.code == 404 and method == "DELETE":
            return
        raise


def _management_api_get(url: str, user: str, password: str) -> dict[str, Any]:
    """GETs `url` and returns the decoded JSON body

    Raises:
        LookupError: the broker answered 404 (e.g. the queried queue is not there yet)
        OSError: the broker could not be reached
    """
    request = urllib.request.Request(url, method="GET")  # noqa: S310
    request.add_header("Accept", "application/json")
    request.add_header("Authorization", f"Basic {b64encode(f'{user}:{password}'.encode()).decode()}")
    try:
        with urllib.request.urlopen(request, timeout=_MGMT_API_TIMEOUT_S) as response:  # noqa: S310
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            msg = f"{url} answered 404"
            raise LookupError(msg) from exc
        raise


def _create_vhost(management_url: str, vhost: str, user: str, password: str) -> None:
    with log_context(logging.INFO, f"creating RabbitMQ vhost '{vhost}' on {management_url}", logger=_logger):
        quoted_vhost = quote(vhost, safe="")
        _management_api_request("PUT", f"{management_url}/api/vhosts/{quoted_vhost}", user, password)
        _management_api_request(
            "PUT",
            f"{management_url}/api/permissions/{quoted_vhost}/{user}",
            user,
            password,
            body={"configure": ".*", "write": ".*", "read": ".*"},
        )


def _delete_vhost(management_url: str, vhost: str, user: str, password: str) -> None:
    with log_context(logging.INFO, f"deleting RabbitMQ vhost '{vhost}' on {management_url}", logger=_logger):
        _management_api_request("DELETE", f"{management_url}/api/vhosts/{quote(vhost, safe='')}", user, password)


@pytest.fixture(scope="module")
def _rabbit_worker_vhost(
    docker_stack: dict, env_vars_for_docker_compose: EnvVarsDict, request: pytest.FixtureRequest
) -> Iterator[str]:
    """Isolates each xdist worker's RabbitMQ traffic in its own vhost on the SAME shared
    broker: some exchanges/queues (e.g. comp_scheduler broadcasts, `aio_pika`'s own hardcoded
    "rpc.dlx" RPC exchange) use fixed, non-worker-scoped names, so concurrent workers sharing
    the default vhost cross-talk. No-op (default vhost "/") when not running under xdist.

    NOTE: module-scoped (not session-scoped) to match `docker_stack`'s scope: a fixture cannot
    depend on one with a narrower scope.
    """
    if not is_xdist_worker(request):
        yield "/"
        return

    worker_id = get_worker_id(request)
    prefix = env_vars_for_docker_compose["SWARM_STACK_NAME"]
    assert f"{prefix}_rabbit" in docker_stack["services"]
    management_url = _get_management_url(prefix)
    user = env_vars_for_docker_compose["RABBIT_USER"]
    password = env_vars_for_docker_compose["RABBIT_PASSWORD"]
    vhost = f"pytest_{worker_id}"

    _create_vhost(management_url, vhost, user, password)
    yield vhost
    _delete_vhost(management_url, vhost, user, password)


@pytest.fixture(scope="module")
def rabbit_management_url(docker_stack: dict, env_vars_for_docker_compose: EnvVarsDict) -> str:
    """Base URL of the management API of the stack's `rabbit` service"""
    prefix = env_vars_for_docker_compose["SWARM_STACK_NAME"]
    assert f"{prefix}_rabbit" in docker_stack["services"]
    return _get_management_url(prefix)


@pytest.fixture
def wait_till_queue_has_consumer(
    rabbit_management_url: str,
    env_vars_for_docker_compose: EnvVarsDict,
) -> Callable[[str, str], Awaitable[None]]:
    """Returns a coroutine that waits until `queue_name` has a consumer in `vhost`

    `RabbitMQClient.subscribe()` returns once the broker answered, but while the broker is
    restarting (e.g. a test rescheduled its swarm task) aio-pika only *warns* about the refused
    connect: the call completes with the queue neither declared nor bound, and the exchange drops
    everything published meanwhile. Gating on the queue having a consumer turns that silent message
    loss into a setup failure.
    """
    user = env_vars_for_docker_compose["RABBIT_USER"]
    password = env_vars_for_docker_compose["RABBIT_PASSWORD"]

    def _not_ready_yet(exc: BaseException) -> bool:
        return _is_transient_network_error(exc) or isinstance(exc, LookupError)

    @tenacity.retry(
        retry=retry_if_exception(_not_ready_yet),
        wait=wait_fixed(1),
        stop=stop_after_delay(_MGMT_API_RETRY_TIMEOUT_S),
        before_sleep=before_sleep_log(_logger, logging.INFO),
        reraise=True,
    )
    async def _wait(queue_name: str, vhost: str) -> None:
        url = f"{rabbit_management_url}/api/queues/{quote(vhost, safe='')}/{quote(queue_name, safe='')}"
        # the management API is plain HTTP: poll it off the event loop
        info = await asyncio.to_thread(_management_api_get, url, user, password)
        # NOTE: the broker leaves `consumers` out of the response while it is zero, so both
        # representations of "has a consumer" are checked
        has_consumer = bool(info.get("consumers") or info.get("consumer_details"))
        if not has_consumer:
            msg = f"queue '{queue_name}' in vhost '{vhost}' has no consumers yet"
            raise LookupError(msg)

    return _wait


@pytest.fixture
def wait_till_rabbit_client_is_connected() -> Callable[[RabbitMQClient], Awaitable[None]]:
    """Returns a coroutine that waits until `client` holds a live connection to the broker

    Complements `wait_till_queue_has_consumer` on the publishing side: while a client is still
    reconnecting, its publishes never reach the broker.
    """

    async def _wait(client: RabbitMQClient, *, timeout_s: float = _MGMT_API_RETRY_TIMEOUT_S) -> None:
        async for attempt in AsyncRetrying(
            stop=stop_after_delay(timeout_s),
            wait=wait_fixed(1),
            retry=retry_if_exception_type(AssertionError),
            before_sleep=before_sleep_log(_logger, logging.INFO),
            reraise=True,
        ):
            with attempt:
                assert await client.ping(), f"{client.client_name} cannot reach RabbitMQ"
                # coarse on purpose: `healthy` keeps reporting True for a grace period after a
                # disconnect. It only rules out a client that has been down for longer than that,
                # the consumer-side gate is what catches a message the broker cannot route.
                assert client.healthy, f"{client.client_name} has been disconnected from RabbitMQ"

    return _wait


@pytest.fixture
def rabbit_env_vars_dict(
    docker_stack: dict,
    env_vars_for_docker_compose: EnvVarsDict,
    _rabbit_worker_vhost: str,
) -> EnvVarsDict:
    prefix = env_vars_for_docker_compose["SWARM_STACK_NAME"]
    assert f"{prefix}_rabbit" in docker_stack["services"]

    port = get_service_published_port("rabbit", int(env_vars_for_docker_compose["RABBIT_PORT"]), stack_name=prefix)

    return {
        "RABBIT_USER": env_vars_for_docker_compose["RABBIT_USER"],
        "RABBIT_PASSWORD": env_vars_for_docker_compose["RABBIT_PASSWORD"],
        "RABBIT_HOST": get_localhost_ip(),
        "RABBIT_PORT": f"{port}",
        "RABBIT_SECURE": env_vars_for_docker_compose["RABBIT_SECURE"],
        "RABBIT_VHOST": _rabbit_worker_vhost,
    }


@pytest.fixture
async def rabbit_settings(rabbit_env_vars_dict: EnvVarsDict) -> RabbitSettings:
    """Returns the settings of a rabbit service that is up and responsive"""

    settings = RabbitSettings.model_validate(rabbit_env_vars_dict)
    with log_context(
        logging.INFO, f"waiting for RabbitMQ on vhost '{settings.RABBIT_VHOST}' to be responsive", logger=_logger
    ):
        await wait_till_rabbit_responsive(settings.dsn)
    return settings


@pytest.fixture
async def rabbit_service(rabbit_settings: RabbitSettings, monkeypatch: pytest.MonkeyPatch) -> RabbitSettings:
    """Sets env vars for a rabbit service is up and responsive and returns its settings as well

    NOTE: Use this fixture to setup client app
    """
    monkeypatch.setenv("RABBIT_HOST", rabbit_settings.RABBIT_HOST)
    monkeypatch.setenv("RABBIT_PORT", f"{rabbit_settings.RABBIT_PORT}")
    monkeypatch.setenv("RABBIT_USER", rabbit_settings.RABBIT_USER)
    monkeypatch.setenv("RABBIT_SECURE", f"{rabbit_settings.RABBIT_SECURE}")
    monkeypatch.setenv("RABBIT_PASSWORD", rabbit_settings.RABBIT_PASSWORD.get_secret_value())
    # NOTE: must propagate the per-worker vhost, otherwise apps configured from these envs
    # connect to the default vhost "/" where every xdist worker registers the same fixed
    # auto_delete RPC queue names and races with the other workers' teardown
    monkeypatch.setenv("RABBIT_VHOST", rabbit_settings.RABBIT_VHOST)

    return rabbit_settings


@pytest.fixture
async def create_rabbitmq_client(
    rabbit_service: RabbitSettings,
) -> AsyncIterator[Callable[[str], RabbitMQClient]]:
    created_clients: list[RabbitMQClient] = []

    def _creator(client_name: str, *, heartbeat: int = 60) -> RabbitMQClient:
        # pylint: disable=protected-access
        client = RabbitMQClient(f"pytest_{client_name}", rabbit_service, heartbeat=heartbeat)
        assert client
        assert client._connection_pool  # noqa: SLF001
        assert not client._connection_pool.is_closed  # noqa: SLF001
        assert client._channel_pool  # noqa: SLF001
        assert not client._channel_pool.is_closed  # noqa: SLF001
        assert client.client_name == f"pytest_{client_name}"
        assert client.settings == rabbit_service
        created_clients.append(client)
        return client

    yield _creator

    # cleanup, properly close the clients
    await asyncio.gather(*(client.close() for client in created_clients))


@pytest.fixture
async def rabbitmq_rpc_client(
    rabbit_service: RabbitSettings,
) -> AsyncIterator[Callable[[str], Awaitable[RabbitMQRPCClient]]]:
    created_clients = []

    async def _creator(client_name: str, *, heartbeat: int = 60) -> RabbitMQRPCClient:
        client = await RabbitMQRPCClient.create(
            client_name=f"pytest_{client_name}",
            settings=rabbit_service,
            heartbeat=heartbeat,
        )
        assert client
        assert client.client_name == f"pytest_{client_name}"
        assert client.settings == rabbit_service
        created_clients.append(client)
        return client

    yield _creator
    # cleanup, properly close the clients
    await asyncio.gather(*(client.close() for client in created_clients))


@pytest.fixture
async def ensure_parametrized_queue_is_empty(
    create_rabbitmq_client: Callable[[str], RabbitMQClient], queue_name: QueueName
) -> AsyncIterator[None]:
    rabbitmq_client = create_rabbitmq_client("pytest-purger")

    async def _queue_messages_purger() -> None:
        # NOTE: a passive get_queue() on a non-existing queue makes the broker close the
        # channel (ChannelNotFoundEntity), which would poison the client's channel pool if
        # that channel got reused. So we use a dedicated channel here and always close it,
        # instead of going through `rabbitmq_client._channel_pool.acquire()`.
        channel = await rabbitmq_client._get_channel()  # noqa: SLF001
        try:
            assert isinstance(channel, aio_pika.RobustChannel)
            queue = await channel.get_queue(queue_name)
            await queue.purge()
        except aio_pika.exceptions.ChannelNotFoundEntity:
            # queue does not exist (yet): nothing to purge
            pass
        finally:
            with contextlib.suppress(Exception):
                await channel.close()

    await _queue_messages_purger()
    yield
    # cleanup
    await _queue_messages_purger()
