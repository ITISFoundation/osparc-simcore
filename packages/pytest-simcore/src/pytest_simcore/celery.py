import datetime
from collections.abc import AsyncIterator
from typing import Any

import pytest
from celery import Celery
from celery_library.backends.redis import RedisTaskStore
from celery_library.task_manager import CeleryTaskManager
from celery_library.types import register_celery_types
from servicelib.celery.task_manager import TaskManager
from servicelib.redis import RedisClientSDK
from settings_library.celery import CelerySettings
from settings_library.redis import RedisDatabase, RedisSettings


@pytest.fixture(scope="session")
def celery_config() -> dict[str, Any]:
    return {
        "broker_connection_retry_on_startup": True,
        "broker_url": "memory://localhost//",
        "result_backend": "cache+memory://localhost//",
        "result_expires": datetime.timedelta(days=7),
        "result_extended": True,
        "pool": "threads",
        "task_default_queue": "default",
        "task_send_sent_event": True,
        "task_track_started": True,
        "worker_send_task_events": True,
    }


@pytest.fixture
async def celery_task_manager(
    mock_celery_app: Celery,
    celery_settings: CelerySettings,
    use_in_memory_redis: RedisSettings,
) -> AsyncIterator[TaskManager]:
    register_celery_types()

    try:
        redis_client_sdk = RedisClientSDK(
            use_in_memory_redis.build_redis_dsn(RedisDatabase.CELERY_TASKS),
            client_name="pytest_celery_tasks",
        )
        await redis_client_sdk.setup()

        yield CeleryTaskManager(
            mock_celery_app,
            celery_settings,
            RedisTaskStore(redis_client_sdk),
        )
    finally:
        await redis_client_sdk.shutdown()
