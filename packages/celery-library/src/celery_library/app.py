import ssl
from typing import Any

from celery import Celery  # type: ignore[import-untyped]
from settings_library.celery import CelerySettings
from settings_library.redis import RedisDatabase


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
