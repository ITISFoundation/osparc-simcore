# pylint: disable=redefined-outer-name

from contextlib import asynccontextmanager
from typing import Any

import pytest
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_extension import (
    _MAPPER_MESSAGE_HANDLERS,
    _MAPPER_MODEL_TYPE,
    MessageType,
    NamespacedMethodResolver,
    RabbitMessageQueryForLabels,
    RabbitMessageRemoveNamespacedMethod,
    RabbitMessageUpdateNamespacedMethod,
    RabbitNamespacedNameResolver,
    _parse_data,
)
from settings_library.rabbit import RabbitSettings
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
]


@asynccontextmanager
async def get_rabbit_namespaced_resolver(
    rabbit_service: RabbitSettings, client_name: str
) -> RabbitNamespacedNameResolver:
    client = RabbitMQClient(client_name=client_name, settings=rabbit_service)
    await client.rpc_initialize()
    yield RabbitNamespacedNameResolver(
        namespaced_resolver=NamespacedMethodResolver(), rabbit_client=client
    )
    await client.close()


@pytest.fixture
async def requester_resolver(
    rabbit_service: RabbitSettings,
) -> RabbitNamespacedNameResolver:
    async with get_rabbit_namespaced_resolver(rabbit_service, "requester") as resolver:
        yield resolver


@pytest.fixture
async def replier_resolver(
    rabbit_service: RabbitSettings,
) -> RabbitNamespacedNameResolver:
    async with get_rabbit_namespaced_resolver(rabbit_service, "replier") as resolver:
        yield resolver


@pytest.mark.parametrize(
    "stored_data, query_data, mixed_types",
    [
        pytest.param(["hello", "2000"], ["2000", "hello"], False, id="list"),
        pytest.param(("hello", "2000"), ("2000", "hello"), False, id="tuple"),
        pytest.param({"hello", "2000"}, {"2000", "hello"}, False, id="set"),
        pytest.param({"hello", "2000"}, {"2000", "hello"}, False, id="inverted_set"),
        pytest.param({"hello", 2000}, {"2000", "hello"}, True, id="set_mixed_types"),
        pytest.param(
            {"hello", 2000}, {"2000", "hello"}, True, id="inverted_set_mixed_types"
        ),
        pytest.param(
            ["hello", "2000", "2000"],
            ["2000", "hello"],
            False,
            id="list_with_duplicate_entries",
        ),
        pytest.param(
            ["hello", "2000", 2000],
            ["2000", "hello"],
            True,
            id="list_with_duplicate_entries_and_mixed",
        ),
    ],
)
def test_namespaced_method_resolver(
    stored_data: Any, query_data: Any, mixed_types: bool
) -> None:
    resolver = NamespacedMethodResolver()
    method_name = "m1"

    resolver.add(method_name, stored_data)
    assert resolver.get_namespaced_method(stored_data) == method_name

    # the provided labels always get transformed to strings
    # and are all duplicates are removed
    assert resolver.get_namespaced_method(query_data) == method_name is not mixed_types

    resolver.remove(method_name, query_data)
    assert resolver.get_namespaced_method(stored_data) is None


@pytest.mark.parametrize(
    "data, expected_type",
    [
        (
            RabbitMessageQueryForLabels(labels={""}).json(),
            RabbitMessageQueryForLabels,
        ),
        (
            RabbitMessageRemoveNamespacedMethod(
                labels={""}, namespaced_method=""
            ).json(),
            RabbitMessageRemoveNamespacedMethod,
        ),
        (
            RabbitMessageUpdateNamespacedMethod(
                labels={""}, namespaced_method=""
            ).json(),
            RabbitMessageUpdateNamespacedMethod,
        ),
    ],
)
def test_parse_data(data: bytes, expected_type: type):
    result = _parse_data(data)
    assert type(result) == expected_type


def test_mappers_contain_all_message_type_entries():
    message_type_entries = {  # pylint:disable=unnecessary-comprehension
        x for x in MessageType
    }
    assert set(_MAPPER_MESSAGE_HANDLERS.keys()) == message_type_entries
    assert set(_MAPPER_MODEL_TYPE.keys()) == message_type_entries


async def test_rabbit_namespaced_name_resolver_workflow(
    requester_resolver: RabbitNamespacedNameResolver,
    replier_resolver: RabbitNamespacedNameResolver,
) -> None:
    expected_method_name = "test_method"
    labels_to_match = {2000, "hello"}

    # TODO: use an array of requester and pick one randomly from the array to run the test

    replier_resolver.namespaced_resolver.add(expected_method_name, {"hello", 2000})
    assert (
        requester_resolver.namespaced_resolver.get_namespaced_method(labels_to_match)
        is None
    )

    await replier_resolver.start()
    await requester_resolver.start()

    # try to resolve namespaced method name for the labels
    result = await requester_resolver.get_namespaced_method_for(labels_to_match)
    assert result == expected_method_name

    # TODO: use tenacity here

    # once the method is resolved the result is also distributed to all the instances that are listening
    assert (
        replier_resolver.namespaced_resolver.get_namespaced_method(labels_to_match)
        == expected_method_name
    )
    assert (
        requester_resolver.namespaced_resolver.get_namespaced_method(labels_to_match)
        == expected_method_name
    )

    # send a request to remove method for the labels
    await requester_resolver.remove_namespaced_method_with(
        expected_method_name, {"hello", 2000}
    )

    # check that keys are removed everywhere
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1), stop=stop_after_delay(2), reraise=True
    ):
        with attempt:
            assert (
                requester_resolver.namespaced_resolver.get_namespaced_method(
                    labels_to_match
                )
                is None
            )
            assert (
                replier_resolver.namespaced_resolver.get_namespaced_method(
                    labels_to_match
                )
                is None
            )


# TODO timeout test
