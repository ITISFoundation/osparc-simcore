# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from typing import Any, Awaitable, Callable, Final

import pytest
from docker.client import DockerClient
from docker.models.containers import Container
from pydantic import NonNegativeInt, ValidationError
from pytest import LogCaptureFixture
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_errors import (
    RemoteMethodNotRegisteredError,
    RPCNotInitializedError,
)
from servicelib.rabbitmq_utils import RPCNamespace, rpc_register_entries
from settings_library.rabbit import RabbitSettings

pytest_simcore_core_services_selection = [
    "rabbit",
]

MULTIPLE_REQUESTS_COUNT: Final[NonNegativeInt] = 100

# FIXTURES


@pytest.fixture
def namespace() -> RPCNamespace:
    return RPCNamespace.from_entries({f"test{i}": f"test{i}" for i in range(8)})


@pytest.fixture
async def rabbit_requester(rabbit_service: RabbitSettings) -> RabbitMQClient:
    client = RabbitMQClient(client_name="requester", settings=rabbit_service)
    await client.rpc_initialize()
    yield client
    await client.close()


@pytest.fixture
async def rabbit_replier(rabbit_service: RabbitSettings) -> RabbitMQClient:
    client = RabbitMQClient(client_name="replier", settings=rabbit_service)
    await client.rpc_initialize()
    yield client
    await client.close()


@pytest.fixture
def restart_rabbit(
    docker_stack: dict,
    testing_environ_vars: dict,
    docker_client: DockerClient,
) -> Callable:
    prefix = testing_environ_vars["SWARM_STACK_NAME"]
    service_name = f"{prefix}_rabbit"
    assert service_name in docker_stack["services"]

    async def _reboot() -> None:
        containers = docker_client.containers.list(
            filters={"label": f"com.docker.swarm.service.name={service_name}"}
        )
        assert len(containers) == 1
        container: Container = containers[0]
        # killing the container will cause the service to be unavailable
        #  and swarm to restart it. Exactly what we are trying to test
        container.kill()

    return _reboot


# UTILS


async def add_me(*, x: Any, y: Any) -> Any:
    result = x + y
    # NOTE: types are not enforced
    # result's type will on the caller side will be the one it has here
    return result


class CustomClass:
    def __init__(self, x: Any, y: Any) -> None:
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} x={self.x}, y={self.y}>"

    def __eq__(self, other: "CustomClass") -> bool:
        return self.x == other.x and self.y == other.y

    def __add__(self, other: "CustomClass") -> "CustomClass":
        return CustomClass(x=self.x + other.x, y=self.y + other.y)


# TESTS


@pytest.mark.parametrize(
    "x,y,expected_result,expected_type",
    [
        pytest.param(12, 20, 32, int, id="expect_int"),
        pytest.param(12, 20.0, 32.0, float, id="expect_float"),
        pytest.param(b"123b", b"xyz0", b"123bxyz0", bytes, id="expect_bytes"),
        pytest.param([1, 2], [2, 3], [1, 2, 2, 3], list, id="list_addition"),
        pytest.param(
            CustomClass(2, 1),
            CustomClass(1, 2),
            CustomClass(3, 3),
            CustomClass,
            id="custom_class",
        ),
        pytest.param(
            CustomClass([{"p", "1"}], [{"h": 1}]),
            CustomClass([{3, b"bytes"}], [{"b": 2}]),
            CustomClass([{"p", "1"}, {3, b"bytes"}], [{"h": 1}, {"b": 2}]),
            CustomClass,
            id="custom_class_complex_objects",
        ),
    ],
)
async def test_base_rpc_pattern(
    rabbit_requester: RabbitMQClient,
    rabbit_replier: RabbitMQClient,
    x: Any,
    y: Any,
    expected_result: Any,
    expected_type: type,
    namespace: RPCNamespace,
):
    await rabbit_replier.rpc_register_handler(namespace, add_me.__name__, add_me)

    request_result = await rabbit_requester.rpc_request(
        namespace, add_me.__name__, x=x, y=y
    )
    assert request_result == expected_result
    assert type(request_result) == expected_type

    await rabbit_replier.rpc_unregister_handler(add_me)


async def test_multiple_requests_sequence_same_replier_and_requester(
    rabbit_requester: RabbitMQClient,
    rabbit_replier: RabbitMQClient,
    namespace: RPCNamespace,
):
    await rabbit_replier.rpc_register_handler(namespace, add_me.__name__, add_me)

    for i in range(MULTIPLE_REQUESTS_COUNT):
        assert (
            await rabbit_requester.rpc_request(
                namespace, add_me.__name__, x=1 + i, y=2 + i
            )
            == 3 + i * 2
        )


async def test_multiple_requests_parallel_same_replier_and_requester(
    rabbit_requester: RabbitMQClient,
    rabbit_replier: RabbitMQClient,
    namespace: RPCNamespace,
):
    await rabbit_replier.rpc_register_handler(namespace, add_me.__name__, add_me)

    expected_result: list[int] = []
    requests: list[Awaitable] = []
    for i in range(MULTIPLE_REQUESTS_COUNT):
        requests.append(
            rabbit_requester.rpc_request(namespace, add_me.__name__, x=1 + i, y=2 + i)
        )
        expected_result.append(3 + i * 2)

    assert await asyncio.gather(*requests) == expected_result


async def test_multiple_requests_parallel_same_replier_different_requesters(
    rabbit_service: RabbitSettings,
    rabbit_replier: RabbitMQClient,
    namespace: RPCNamespace,
):
    await rabbit_replier.rpc_register_handler(namespace, add_me.__name__, add_me)

    clients: list[RabbitMQClient] = []
    for _ in range(MULTIPLE_REQUESTS_COUNT):
        client = RabbitMQClient("", rabbit_service)
        clients.append(client)

    # worst case scenario
    await asyncio.gather(*[c.rpc_initialize() for c in clients])

    requests: list[Awaitable] = []
    expected_result: list[int] = []
    for i in range(MULTIPLE_REQUESTS_COUNT):
        client = clients[i]
        requests.append(
            client.rpc_request(namespace, add_me.__name__, x=1 + i, y=2 + i)
        )
        expected_result.append(3 + i * 2)

    assert await asyncio.gather(*requests) == expected_result

    # worst case scenario
    await asyncio.gather(*[c.close() for c in clients])


async def test_raise_error_if_not_started(
    rabbit_service: RabbitSettings, namespace: RPCNamespace
):
    requester = RabbitMQClient("", settings=rabbit_service)
    with pytest.raises(RPCNotInitializedError):
        await requester.rpc_request(namespace, add_me.__name__, x=1, y=2)

    # expect not to raise error
    await requester.close()

    replier = RabbitMQClient("", settings=rabbit_service)
    with pytest.raises(RPCNotInitializedError):
        await replier.rpc_register_handler(namespace, add_me.__name__, add_me)

    with pytest.raises(RPCNotInitializedError):
        await replier.rpc_unregister_handler(add_me)

    # expect not to raise error
    await replier.close()


async def _assert_event_not_registered(
    rabbit_requester: RabbitMQClient, namespace: RPCNamespace
):
    with pytest.raises(RemoteMethodNotRegisteredError) as exec_info:
        assert (
            await rabbit_requester.rpc_request(namespace, add_me.__name__, x=1, y=3)
            == 3
        )
    assert (
        f"Could not find a remote method named: '{namespace}.{add_me.__name__}'"
        in f"{exec_info.value}"
    )


async def test_replier_not_started(
    rabbit_requester: RabbitMQClient, namespace: RPCNamespace
):
    await _assert_event_not_registered(rabbit_requester, namespace)


async def test_replier_handler_not_registered(
    rabbit_requester: RabbitMQClient,
    rabbit_replier: RabbitMQClient,
    namespace: RPCNamespace,
):
    await _assert_event_not_registered(rabbit_requester, namespace)


async def test_request_is_missing_arguments(
    rabbit_requester: RabbitMQClient,
    rabbit_replier: RabbitMQClient,
    namespace: RPCNamespace,
):
    await rabbit_replier.rpc_register_handler(namespace, add_me.__name__, add_me)

    # missing 1 argument
    with pytest.raises(TypeError) as exec_info:
        await rabbit_requester.rpc_request(namespace, add_me.__name__, x=1)
    assert (
        f"{add_me.__name__}() missing 1 required keyword-only argument: 'y'"
        in f"{exec_info.value}"
    )

    # missing all arguments
    with pytest.raises(TypeError) as exec_info:
        await rabbit_requester.rpc_request(namespace, add_me.__name__)
    assert (
        f"{add_me.__name__}() missing 2 required keyword-only arguments: 'x' and 'y'"
        in f"{exec_info.value}"
    )


async def test_requester_cancels_long_running_request_or_requester_takes_too_much_to_respond(
    rabbit_requester: RabbitMQClient,
    rabbit_replier: RabbitMQClient,
    namespace: RPCNamespace,
):
    async def _long_running(*, time_to_sleep: float) -> None:
        await asyncio.sleep(time_to_sleep)

    await rabbit_replier.rpc_register_handler(
        namespace, _long_running.__name__, _long_running
    )

    with pytest.raises(asyncio.TimeoutError):
        await rabbit_requester.rpc_request(
            namespace, _long_running.__name__, time_to_sleep=3, timeout_s=1
        )


async def test_replier_handler_raises_error(
    rabbit_requester: RabbitMQClient,
    rabbit_replier: RabbitMQClient,
    namespace: RPCNamespace,
):
    async def _raising_error() -> None:
        raise RuntimeError("failed as requested")

    await rabbit_replier.rpc_register_handler(
        namespace, _raising_error.__name__, _raising_error
    )

    with pytest.raises(RuntimeError) as exec_info:
        await rabbit_requester.rpc_request(namespace, _raising_error.__name__)
    assert "failed as requested" == f"{exec_info.value}"


async def test_replier_responds_with_not_locally_defined_object_instance(
    rabbit_requester: RabbitMQClient,
    rabbit_replier: RabbitMQClient,
    namespace: RPCNamespace,
    caplog: LogCaptureFixture,
):
    async def _replier_scope() -> None:
        class Custom:
            def __init__(self, x: Any) -> None:
                self.x = x

        async def _get_custom(x: Any) -> Custom:
            return Custom(x)

        await rabbit_replier.rpc_register_handler(namespace, "a_name", _get_custom)

    async def _requester_scope() -> None:
        # NOTE: what is happening here?
        # the replier will say that it cannot pickle a local object and send it over
        # the server's request will just time out. I would prefer a cleaner interface.
        # There is no change of intercepting this message.
        with pytest.raises(asyncio.TimeoutError):
            await rabbit_requester.rpc_request(namespace, "a_name", x=10, timeout_s=1)

        assert "Can't pickle local object" in caplog.text
        assert ".<locals>.Custom" in caplog.text

    await _replier_scope()
    await _requester_scope()


async def test_register_handler_under_same_name_raises_error(
    rabbit_replier: RabbitMQClient, namespace: RPCNamespace
):
    async def _a_handler() -> None:
        pass

    async def _another_handler() -> None:
        pass

    await rabbit_replier.rpc_register_handler(namespace, "same_name", _a_handler)
    with pytest.raises(RuntimeError) as exec_info:
        await rabbit_replier.rpc_register_handler(
            namespace, "same_name", _another_handler
        )
    assert "Method name already used for" in f"{exec_info.value}"


async def test_rpc_register_for_is_equivalent_to_rpc_register(
    rabbit_replier: RabbitMQClient,
):
    namespace_entries = {"hello": "test", "1": "me"}
    namespace = RPCNamespace.from_entries(namespace_entries)

    async def _a_handler() -> int:
        return 42

    async def _assert_call_ok():
        result = await rabbit_replier.rpc_request(namespace, "_a_handler")
        assert result == 42

    await rabbit_replier.rpc_register_handler(namespace, "_a_handler", _a_handler)
    await _assert_call_ok()

    await rabbit_replier.rpc_unregister_handler(_a_handler)

    await rpc_register_entries(rabbit_replier, namespace_entries, _a_handler)
    await _assert_call_ok()


@pytest.mark.parametrize(
    "handler_name, expect_fail",
    [
        ("a" * 254, True),
        ("a" * 253, False),
    ],
)
async def test_get_namespaced_method_name_max_length(
    rabbit_replier: RabbitMQClient, handler_name: str, expect_fail: bool
):
    async def _a_handler() -> None:
        pass

    if expect_fail:
        with pytest.raises(ValidationError) as exec_info:
            await rabbit_replier.rpc_register_handler("a", handler_name, _a_handler)
        assert "ensure this value has at most 255 characters" in f"{exec_info.value}"
    else:
        await rabbit_replier.rpc_register_handler("a", handler_name, _a_handler)


async def test_rabbit_unavailable_just_before_request(
    rabbit_requester: RabbitMQClient,
    rabbit_replier: RabbitMQClient,
    namespace: RPCNamespace,
    restart_rabbit: Callable,
):
    times_called = 0

    async def _func() -> None:
        nonlocal times_called
        times_called += 1

    await rabbit_replier.rpc_register_handler(namespace, _func.__name__, _func)

    await restart_rabbit()

    # this function will be retried because rabbitmq is restarting
    await rabbit_requester.rpc_request(namespace, _func.__name__)

    assert times_called == 1


async def test_rabbit_unavailable_during_request(
    rabbit_requester: RabbitMQClient,
    rabbit_replier: RabbitMQClient,
    namespace: RPCNamespace,
    restart_rabbit: Callable,
):
    times_called = 0

    sleep_duration = 5

    async def _long_running_call() -> None:
        nonlocal times_called
        times_called += 1
        await asyncio.sleep(sleep_duration)

    await rabbit_replier.rpc_register_handler(
        namespace, _long_running_call.__name__, _long_running_call
    )

    task = asyncio.create_task(
        rabbit_requester.rpc_request(
            namespace, _long_running_call.__name__, timeout_s=sleep_duration * 1.1
        )
    )

    await restart_rabbit()
    await task

    assert times_called == 1
