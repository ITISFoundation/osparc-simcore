import ssl
from typing import Any

from celery import Celery  # type: ignore[import-untyped]
from servicelib.redis import RedisClientSDK
from settings_library.celery import CelerySettings
from settings_library.redis import RedisDatabase

from .backends._redis import RedisTaskInfoStore
from .task_manager import CeleryTaskManager


def _celery_configure(celery_settings: CelerySettings) -> dict[str, Any]:
    base_config = {
        "broker_connection_retry_on_startup": True,
        "result_expires": celery_settings.CELERY_RESULT_EXPIRES,
        "result_extended": True,
        "result_serializer": "json",
        "task_default_queue": "default",
        "task_send_sent_event": True,
        "task_track_started": True,
        "worker_send_task_events": True,
    }
    if celery_settings.CELERY_REDIS_RESULT_BACKEND.REDIS_SECURE:
        base_config["redis_backend_use_ssl"] = {"ssl_cert_reqs": ssl.CERT_NONE}
    return base_config


def create_app(settings: CelerySettings) -> Celery:
    assert settings

    return Celery(
        broker=settings.CELERY_RABBIT_BROKER.dsn,
        backend=settings.CELERY_REDIS_RESULT_BACKEND.build_redis_dsn(
            RedisDatabase.CELERY_TASKS,
        ),
        **_celery_configure(settings),
    )


async def create_task_manager(
    app: Celery, settings: CelerySettings
) -> CeleryTaskManager:
    redis_client_sdk = RedisClientSDK(
        settings.CELERY_REDIS_RESULT_BACKEND.build_redis_dsn(
            RedisDatabase.CELERY_TASKS
        ),
        client_name="celery_tasks",
    )
    await redis_client_sdk.setup()
    #

    return CeleryTaskManager(
        app,
        settings,
        RedisTaskInfoStore(redis_client_sdk),
    )
