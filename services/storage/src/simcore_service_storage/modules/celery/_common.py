import logging
import ssl

from celery import Celery  # type: ignore[import-untyped]
from settings_library.celery import CelerySettings
from settings_library.redis import RedisDatabase

_logger = logging.getLogger(__name__)


def create_app(celery_settings: CelerySettings) -> Celery:
    assert celery_settings

    app = Celery(
        broker=celery_settings.CELERY_RABBIT_BROKER.dsn,
        backend=celery_settings.CELERY_REDIS_RESULT_BACKEND.build_redis_dsn(
            RedisDatabase.CELERY_TASKS,
        ),
    )
    app.conf.broker_connection_retry_on_startup = True
    # NOTE: disable SSL cert validation (https://github.com/ITISFoundation/osparc-simcore/pull/7407)
    app.conf.redis_backend_use_ssl = {"ssl_cert_reqs": ssl.CERT_NONE}
    app.conf.result_expires = celery_settings.CELERY_RESULT_EXPIRES
    app.conf.result_extended = True  # original args are included in the results
    app.conf.result_serializer = "json"
    app.conf.task_send_sent_event = True
    app.conf.task_track_started = True
    app.conf.worker_send_task_events = True  # enable tasks monitoring

    return app
