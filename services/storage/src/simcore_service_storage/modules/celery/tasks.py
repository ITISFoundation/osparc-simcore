import logging

from celery import current_app

_logger = logging.getLogger(__name__)


def archive(files: list[str]) -> str:
    _logger.error(
        "Archiving: %s (conf=%s)", ", ".join(files), f"{current_app.conf.fastapi_app}"
    )
    return "".join(files)
