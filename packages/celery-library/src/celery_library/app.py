import ssl
from typing import Any

from celery import Celery  # type: ignore[import-untyped]
from models_library.celery import DEFAULT_QUEUE
from pydantic import TypeAdapter
from settings_library.celery import CelerySettings
from settings_library.redis import RedisDatabase


def _celery_configure(celery_settings: CelerySettings) -> dict[str, Any]:
    base_config = {
        "broker_connection_max_retries": None,
        "broker_connection_retry_on_startup": True,
        "broker_connection_retry": True,
        "broker_heartbeat": 30,
        # Redis is in-cluster, so start at 50 ms to recover quickly from a brief
        # disconnect. Three retries limit one operation to four backend calls and,
        # with Celery's full-jitter exponential backoff, add at most 700 ms of sleep
        # (about 350 ms on average). The 500 ms cap bounds each wait if the retry
        # count is increased later.
        "result_backend_always_retry": True,
        "result_backend_max_retries": 3,
        "result_backend_base_sleep_between_retries_ms": 50,
        "result_backend_max_sleep_between_retries_ms": 500,
        "result_expires": celery_settings.CELERY_RESULT_EXPIRES,
        "result_extended": True,
        "result_serializer": "json",
        "task_default_queue": DEFAULT_QUEUE,
        "task_send_sent_event": True,
        "task_track_started": True,
        "worker_hijack_root_logger": False,
        "worker_send_task_events": True,
        # Configure celery to use quorum queues
        # https://docs.celeryq.dev/en/v5.5.2/userguide/configuration.html#std-setting-task_default_queue_type
        # https://github.com/celery/celery/issues/6067#issuecomment-2212577881
        # See See https://github.com/ITISFoundation/osparc-simcore/pull/8573
        # to know why we need quorum queues
        "task_default_queue_type": "quorum",
        "broker_transport_options": {"confirm_publish": True},
        "worker_detect_quorum_queues": True,
    }
    if celery_settings.CELERY_REDIS_RESULT_BACKEND.REDIS_SECURE:
        base_config["redis_backend_use_ssl"] = {"ssl_cert_reqs": TypeAdapter(bool).validate_python(ssl.CERT_NONE)}
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
