import logging
from os.path import join
from pathlib import Path

from aiohttp import web
from simcore_service_webserver.products import get_product_template_path

from .._resources import resources
from ..email_core import AttachmentTuple, send_email_from_template

log = logging.getLogger(__name__)


def themed(dirname: str, template: str) -> Path:
    return resources.get_path(join(dirname, template))


async def get_template_path(request: web.Request, filename: str) -> Path:
    return await get_product_template_path(request, filename)


# prevents auto-removal by pycln
assert AttachmentTuple  # nosec
assert send_email_from_template  # nosec


__all__: tuple[str, ...] = (
    "AttachmentTuple",
    "send_email_from_template",
)
