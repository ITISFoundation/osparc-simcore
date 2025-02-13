import logging

_log = logging.getLogger(__name__)


def archive(files: list[str]) -> None:
    _log.info("Archiving: %s", ", ".join(files))
