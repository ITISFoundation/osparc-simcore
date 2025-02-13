import logging

_log = logging.getLogger(__name__)


def archive(files: list[str]) -> str:
    _log.info("Archiving: %s", ", ".join(files))
    return "".join(files)
