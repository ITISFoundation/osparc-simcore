# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from unittest import mock

from fastapi import FastAPI
from simcore_service_resource_usage_tracker.services.modules.redis import (
    get_redis_lock_client,
)


async def test_redis_raises_if_missing(
    disabled_prometheus: None,
    disabled_database: None,
    disabled_rabbitmq: None,
    mocked_setup_rabbitmq: mock.Mock,
    mocked_redis_server: None,
    initialized_app: FastAPI,
):
    client = get_redis_lock_client(initialized_app)
    assert await client.ping() is True
