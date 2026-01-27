import logging

from ._core import AttachmentTuple, get_template_path, send_email_from_template

log = logging.getLogger(__name__)


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
