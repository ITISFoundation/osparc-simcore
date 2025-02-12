import logging

from celery import Celery

_log = logging.getLogger(__name__)


def archive(files: list[str]) -> None:
    _log.info(f"Archiving {files=}")


def setup_celery_tasks(celery_app: Celery) -> None:
    celery_app.task()(archive)
