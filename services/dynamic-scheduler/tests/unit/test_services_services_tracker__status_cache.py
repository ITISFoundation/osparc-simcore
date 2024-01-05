# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.services_tracker._status_cache import (
    ServiceStatusCache,
)
from tenacity import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "redis",
]


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    redis_service: RedisSettings,
) -> EnvVarsDict:
    return app_environment


@dataclass
class CustomPyObject:
    a_value: int
    ok: bool


@pytest.mark.parametrize(
    "obj",
    [
        42,
        "a_str",
        ["a", "list"],
        ("a", "tuple"),
        {"a", "set"},
        {"a": "dict"},
        CustomPyObject(a_value=42, ok=True),
    ],
)
async def test_services_status_cache_workflow(
    disable_rabbitmq_setup: None,
    disable_services_tracker_setup: None,
    app: FastAPI,
    obj: Any,
):
    cache = ServiceStatusCache(app, ttl=0.1, namespace="services_caches")

    # when does nto exist returns nothing
    assert await cache.get_value("missing") is None

    await cache.set_value("existing", obj)
    assert await cache.get_value("existing") == obj

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(2),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            assert await cache.get_value("existing") is None


async def test_service_status_cache_namespace(
    disable_rabbitmq_setup: None, disable_services_tracker_setup: None, app: FastAPI
):
    cache_1 = ServiceStatusCache(app, ttl=0.2, namespace="c1")
    cache_2 = ServiceStatusCache(app, ttl=0.2, namespace="c2")

    key_1 = "key_1"
    key_2 = "key_2"

    value_1 = 1
    value_2 = "ok"

    await cache_1.set_value(key_1, value_1)

    assert await cache_1.get_value(key_1) == value_1
    assert await cache_2.get_value(key_1) is None
    assert await cache_1.get_value(key_2) is None
    assert await cache_2.get_value(key_2) is None

    await cache_2.set_value(key_2, value_2)

    assert await cache_1.get_value(key_1) == value_1
    assert await cache_2.get_value(key_1) is None
    assert await cache_1.get_value(key_2) is None
    assert await cache_2.get_value(key_2) == value_2

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(2),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            assert await cache_1.get_value(key_1) is None
            assert await cache_2.get_value(key_1) is None
            assert await cache_1.get_value(key_2) is None
            assert await cache_2.get_value(key_2) is None
