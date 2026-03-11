import logging
from pathlib import Path

from .._resources import webserver_resources
from ..email.email_service import (
    AttachmentTuple,
    get_template_path,
    send_email_from_template,
)

log = logging.getLogger(__name__)


def themed(dirname: str, template: str) -> Path:
    path: Path = webserver_resources.get_path(f"{Path(dirname) / template}")
    return path


# prevents auto-removal by pycln
# mypy: disable-error-code=truthy-function
assert AttachmentTuple  # nosec
assert send_email_from_template  # nosec
assert get_template_path  # nosec


__all__: tuple[str, ...] = (
    "AttachmentTuple",
    "get_template_path",
    "send_email_from_template",
)
