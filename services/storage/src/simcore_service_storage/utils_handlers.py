""" This module is to encourage reusing common functionality on handler modules

    Drop here any helper function commonly used in handler modules and that has no other place to
    be. Later could be moved to a more convenient module
"""

from aiohttp.web import Request
from servicelib.rest_utils import extract_and_validate

from .dsm import DataStorageManager


def create_storage_manager(
    request: Request,
):

    # TODO: minimum to request

    DataStorageManager()


async def validate_request(request: Request):
    params, query, body = await extract_and_validate(request)

    dsm = await _prepare_storage_manager(params, query, request)
