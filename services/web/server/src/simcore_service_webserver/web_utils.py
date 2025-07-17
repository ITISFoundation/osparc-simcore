from dataclasses import asdict
from typing import Any

from aiohttp import web
from common_library.json_serialization import json_dumps
from models_library.rest_error import LogMessageType
from servicelib.aiohttp.status import HTTP_200_OK


def envelope_response(data: Any, *, status: int = HTTP_200_OK) -> web.Response:
    return web.json_response(
        {
            "data": data,
            "error": None,
        },
        dumps=json_dumps,
        status=status,
    )


def flash_response(
    message: str, level: str = "INFO", *, status: int = HTTP_200_OK
) -> web.Response:
    return envelope_response(
        data=asdict(LogMessageType(message, level)),
        status=status,
    )
