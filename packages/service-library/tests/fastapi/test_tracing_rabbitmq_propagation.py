# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

"""Regression tests for trace propagation across RabbitMQ.

The OTel instrumentors (in particular ``AioPikaInstrumentor``) decorate the
consumer callback at ``queue.consume()`` registration time. Therefore the
instrumentation must be active *before* any RabbitMQ consumer (pub/sub
subscription or RPC handler) is registered, otherwise the incoming
``traceparent`` header is never extracted and the consumer side starts an
orphan trace.

Commit fe38fef2d ("lazy OTel tracing startup") moved ``_startup()`` from
setup-time into the tracing lifespan step itself, which broke services that
register their RabbitMQ consumers in an earlier lifespan step (e.g.
dynamic-scheduler). These tests pin the required behavior: after wiring an app
with the RabbitMQ consumers registered *before* the tracing lifespan, trace
context must still propagate publisher -> consumer.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractContextManager
from typing import Any, Final

import pytest
from asgi_lifespan import LifespanManager as ASGILifespanManager
from faker import Faker
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from models_library.rabbitmq_basic_types import RPCNamespace
from models_library.rabbitmq_messages import LoggerRabbitMessage, RabbitMessageBase
from models_library.users import UserID
from opentelemetry import trace
from opentelemetry.instrumentation.aio_pika.aio_pika_instrumentor import (
    AioPikaInstrumentor,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.fastapi.rabbitmq import get_rabbitmq_client
from servicelib.fastapi.rabbitmq_lifespan import configure_rabbitmq_client
from servicelib.fastapi.tracing import get_tracing_instrumentation_lifespan
from servicelib.rabbitmq import BIND_TO_ALL_TOPICS, RabbitMQRPCClient
from servicelib.tracing import TracingConfig
from settings_library.rabbit import RabbitSettings
from settings_library.tracing import TracingSettings
from tenacity import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

# Selection of core services started by the docker-swarm fixtures
pytest_simcore_core_services_selection = [
    "rabbit",
]
pytest_simcore_ops_services_selection: list[str] = []

_TRACING_ENV_VARS: Final[dict[str, str]] = {
    "TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT": "http://opentelemetry-collector",
    "TRACING_OPENTELEMETRY_COLLECTOR_PORT": "4318",
    "TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY": "1.0",
    "TRACING_OPENTELEMETRY_COLLECTOR_IMAGE_VERSION": "0.144.0",
}

_MESSAGE_DELIVERY_TIMEOUT_SECS: Final[float] = 30
_MESSAGE_DELIVERY_RETRY_INTERVAL_SECS: Final[float] = 0.1


class _MessageDeliveryRetryPolicy:
    """Retry policy for waiting on asynchronous RabbitMQ message delivery in tests"""

    def __init__(self):
        self.kwargs: dict[str, Any] = {
            "retry": retry_if_exception_type(AssertionError),
            "wait": wait_fixed(_MESSAGE_DELIVERY_RETRY_INTERVAL_SECS),
            "stop": stop_after_delay(_MESSAGE_DELIVERY_TIMEOUT_SECS),
            "reraise": True,
        }


_MESSAGE_DELIVERY_RETRY_POLICY: Final = _MessageDeliveryRetryPolicy()


# a failing test can leave AioPikaInstrumentor patched (its lifespan shutdown is skipped
# when an assertion raises inside the app lifespan), which would let a later test pass for
# the wrong reason, so explicit injection everywhere is impractical
@pytest.fixture(autouse=True)
def _clean_aio_pika_instrumentation_state() -> None:
    with contextlib.suppress(Exception):
        AioPikaInstrumentor().uninstrument()


@pytest.fixture
def rabbit_message(faker: Faker) -> RabbitMessageBase:
    # NOTE: ProjectID/NodeID are plain UUID aliases; UserID is a NewType
    return LoggerRabbitMessage(
        user_id=UserID(faker.pyint(min_value=1)),
        project_id=faker.uuid4(cast_to=None),
        node_id=faker.uuid4(cast_to=None),
        messages=faker.pylist(allowed_types=(str,)),
    )


@pytest.fixture
def enabled_rabbitmq(rabbit_env_vars_dict: EnvVarsDict, monkeypatch: pytest.MonkeyPatch) -> RabbitSettings:
    setenvs_from_dict(monkeypatch, rabbit_env_vars_dict)
    return RabbitSettings.create_from_envs()


@pytest.fixture
def tracing_settings(monkeypatch: pytest.MonkeyPatch) -> TracingSettings:
    setenvs_from_dict(monkeypatch, dict(_TRACING_ENV_VARS))
    return TracingSettings.create_from_envs()


@pytest.fixture
def tracing_config(tracing_settings: TracingSettings, faker: Faker) -> TracingConfig:
    return TracingConfig.create(tracing_settings=tracing_settings, service_name=faker.pystr())


@pytest.fixture
def get_current_trace_id() -> Callable[[], int]:
    def _current_trace_id() -> int:
        return trace.get_current_span().get_span_context().trace_id

    return _current_trace_id


def _publish_span(tracing_config: TracingConfig, name: str) -> AbstractContextManager[trace.Span]:
    tracer = trace.get_tracer("test-publisher", tracer_provider=tracing_config.tracer_provider)
    return tracer.start_as_current_span(name)


@pytest.mark.regression
async def test_regression_trace_context_propagates_to_consumer_registered_before_tracing_startup(
    enabled_rabbitmq: RabbitSettings,
    tracing_config: TracingConfig,
    mock_otel_collector: InMemorySpanExporter,
    rabbit_message: RabbitMessageBase,
    get_current_trace_id: Callable[[], int],
):
    """A subscription registered before the tracing lifespan must still receive the trace context.

    Mirrors the production wiring where RabbitMQ subscriptions are set up in a
    lifespan step that runs before the tracing instrumentation lifespan.
    """
    received_trace_ids: list[int] = []
    message_received = asyncio.Event()

    async def _message_handler(_data: bytes) -> bool:
        received_trace_ids.append(get_current_trace_id())
        message_received.set()
        return True

    app_lifespan: LifespanManager[FastAPI] = LifespanManager()
    # 1. RabbitMQ client + consumer registration, as in services that subscribe
    #    in their own (earlier) lifespan steps
    configure_rabbitmq_client(
        app_lifespan,
        settings=enabled_rabbitmq,
        client_name="tracing_propagation_consumer",
    )

    async def _register_consumer(_app: FastAPI, _state: State) -> AsyncIterator[State]:
        await get_rabbitmq_client(_app).subscribe(
            rabbit_message.channel_name,
            _message_handler,
            topics=[BIND_TO_ALL_TOPICS] if rabbit_message.routing_key() else None,
        )
        yield {}

    app_lifespan.add(_register_consumer)

    # 2. tracing lifespan registered LAST (this is the order that regressed)
    app_lifespan.add(get_tracing_instrumentation_lifespan(tracing_config=tracing_config))

    app = FastAPI(lifespan=app_lifespan)
    async with ASGILifespanManager(app=app):
        producer = get_rabbitmq_client(app)
        assert producer is not None

        with _publish_span(tracing_config, "user-action") as root_span:
            expected_trace_id = root_span.get_span_context().trace_id
            assert expected_trace_id != 0
            await producer.publish(rabbit_message.channel_name, rabbit_message)

        async for attempt in AsyncRetrying(**_MESSAGE_DELIVERY_RETRY_POLICY.kwargs):
            with attempt:
                assert message_received.is_set(), "message was not consumed"

        # the consumer callback must run within the trace started by the publisher
        assert received_trace_ids == [expected_trace_id], (
            "trace context was NOT propagated through RabbitMQ: the consumer ran "
            f"with trace_id={received_trace_ids[0]:#x} instead of {expected_trace_id:#x}"
        )

        # additionally, the aio_pika consumer span (if any) must belong to the same trace
        consumer_spans = [s for s in mock_otel_collector.get_finished_spans() if s.name.endswith(" receive")]
        assert consumer_spans, "no RabbitMQ consumer span was created at all"
        assert all(s.context is not None and s.context.trace_id == expected_trace_id for s in consumer_spans)


@pytest.mark.regression
async def test_regression_trace_context_propagates_to_rpc_handler_registered_before_tracing_startup(
    enabled_rabbitmq: RabbitSettings,
    tracing_config: TracingConfig,
    mock_otel_collector: InMemorySpanExporter,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    get_current_trace_id: Callable[[], int],
):
    """An RPC handler registered in a lifespan step before the tracing lifespan must receive the trace context.

    ``aio_pika.patterns.RPC.register()`` consumes via ``queue.consume()``, so the same
    registration-order problem applies to RPC handlers as to pub/sub subscribers.
    """
    del enabled_rabbitmq  # settings consumed through the pytest-simcore clients

    server = await rabbitmq_rpc_client("tracing_propagation_rpc_server")
    client = await rabbitmq_rpc_client("tracing_propagation_rpc_client")

    namespace = RPCNamespace.from_entries({"tracing_propagation": "regression"})
    received_trace_ids: list[int] = []

    async def add_me(*, x: int, y: int) -> int:
        received_trace_ids.append(get_current_trace_id())
        return x + y

    async def _register_rpc_handler(_app: FastAPI, _state: State) -> AsyncIterator[State]:
        # register the handler (i.e. consume) BEFORE tracing is started
        await server.register_handler(namespace, add_me.__name__, add_me)
        yield {}

    app_lifespan: LifespanManager[FastAPI] = LifespanManager()
    app_lifespan.add(_register_rpc_handler)
    # tracing lifespan registered LAST (this is the order that regressed)
    app_lifespan.add(get_tracing_instrumentation_lifespan(tracing_config=tracing_config))

    app = FastAPI(lifespan=app_lifespan)
    async with ASGILifespanManager(app=app):
        with _publish_span(tracing_config, "rpc-caller") as root_span:
            expected_trace_id = root_span.get_span_context().trace_id
            assert expected_trace_id != 0
            result = await client.request(namespace, add_me.__name__, x=1, y=2)

        assert result == 3
        assert received_trace_ids == [expected_trace_id], (
            "trace context was NOT propagated through the RabbitMQ RPC hop: the handler ran "
            f"with trace_id={(received_trace_ids[0] if received_trace_ids else 0):#x} "
            f"instead of {expected_trace_id:#x}"
        )
