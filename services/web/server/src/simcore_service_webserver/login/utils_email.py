import logging
from pathlib import Path

from aiohttp import web

from .._resources import webserver_resources
from ..email.utils import AttachmentTuple, send_email_from_template
from ..products import products_web

log = logging.getLogger(__name__)


def themed(dirname: str, template: str) -> Path:
    path: Path = webserver_resources.get_path(f"{Path(dirname) / template}")
    return path


async def get_template_path(request: web.Request, filename: str) -> Path:
    return await products_web.get_product_template_path(request, filename)


# prevents auto-removal by pycln
# mypy: disable-error-code=truthy-function
assert AttachmentTuple  # nosec
assert send_email_from_template  # nosec


__all__: tuple[str, ...] = (
    "AttachmentTuple",
    "send_email_from_template",
)
