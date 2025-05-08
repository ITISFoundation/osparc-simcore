# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from collections.abc import AsyncIterable
from datetime import timedelta

import pytest
from servicelib.resilent_long_running._errors import UnexpectedJobNotFoundError
from servicelib.resilent_long_running._models import (
    JobUniqueId,
    LongRunningNamespace,
    ScheduleModel,
)
from servicelib.resilent_long_running._redis import ClientStoreInterface
from settings_library.redis import RedisSettings

pytest_simcore_core_services_selection = [
    "redis",
]


@pytest.fixture
async def client_store_interface(
    redis_service: RedisSettings, long_running_namespace: LongRunningNamespace
) -> AsyncIterable[ClientStoreInterface]:
    client = ClientStoreInterface(redis_service, long_running_namespace)
    await client.setup()

    await client.redis_sdk.redis.flushdb()

    yield client

    await client.teardown()


@pytest.fixture
def schedule_model() -> ScheduleModel:
    return ScheduleModel(name="a", correlation_id="b", params={}, remaining_attempts=1)


async def test_get_set_delete(
    client_store_interface: ClientStoreInterface,
    unique_id: JobUniqueId,
    schedule_model: ScheduleModel,
    job_timeout: timedelta,
):
    assert await client_store_interface.get(unique_id) is None

    await client_store_interface.set(unique_id, schedule_model, expire=job_timeout)
    assert await client_store_interface.get(unique_id) == schedule_model

    await client_store_interface.remove(unique_id)
    assert await client_store_interface.get(unique_id) is None


async def test_remove_not_existing(client_store_interface: ClientStoreInterface):
    await client_store_interface.remove("missing")


async def test_auto_save_get(
    client_store_interface: ClientStoreInterface,
    unique_id: JobUniqueId,
    schedule_model: ScheduleModel,
    job_timeout: timedelta,
):
    await client_store_interface.set(unique_id, schedule_model, expire=job_timeout)

    assert await client_store_interface.get(unique_id) == schedule_model
    async with client_store_interface.auto_save_get(unique_id) as auto_saved:
        auto_saved.name = "cc"

    assert await client_store_interface.get(unique_id) == auto_saved


async def test_key_does_not_expire(
    client_store_interface: ClientStoreInterface,
    unique_id: JobUniqueId,
    schedule_model: ScheduleModel,
    job_timeout: timedelta,
):
    # check key does not expire
    await client_store_interface.set(unique_id, schedule_model, expire=None)
    assert await client_store_interface.get(unique_id) is not None
    assert await client_store_interface.get_existing(unique_id)

    # wait a bit and key should still be there
    await asyncio.sleep(job_timeout.total_seconds())

    assert await client_store_interface.get(unique_id) is not None
    assert await client_store_interface.get_existing(unique_id)


async def test_key_actually_expires(
    client_store_interface: ClientStoreInterface,
    unique_id: JobUniqueId,
    schedule_model: ScheduleModel,
    job_timeout: timedelta,
):
    await client_store_interface.set(unique_id, schedule_model, expire=job_timeout)
    assert await client_store_interface.get(unique_id) is not None
    assert await client_store_interface.get_existing(unique_id)

    # check that key actially expires
    await asyncio.sleep(job_timeout.total_seconds())

    assert await client_store_interface.get(unique_id) is None
    with pytest.raises(UnexpectedJobNotFoundError):
        await client_store_interface.get_existing(unique_id)


async def test_update_entry_expiry_not_existing(
    client_store_interface: ClientStoreInterface, job_timeout: timedelta
):
    await client_store_interface.update_entry_expiry(
        "missing_asdads", expire=job_timeout
    )
