# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import
import asyncio
import json

import attr
from aiohttp import web
from servicelib.aiohttp.rest_codecs import DataEncoder


@attr.s(auto_attribs=True)
class Data:
    x: int = 3
    y: str = "foo"


class Handlers:
    @staticmethod
    async def get_health_wrong(request: web.Request):
        out = {
            "name": __name__.split(".")[0],
            "version": "1.0",
            "status": "SERVICE_RUNNING",
            "invalid_entry": 125,
        }
        return out

    @staticmethod
    async def get_health(request: web.Request):
        out = {
            "name": __name__.split(".")[0],
            "version": "1.0",
            "status": "SERVICE_RUNNING",
            "api_version": "1.0",
        }
        return out

    @staticmethod
    async def get_dict(request: web.Request):
        return {"x": 3, "y": "3"}

    @staticmethod
    async def get_envelope(request: web.Request):
        data = {"x": 3, "y": "3"}
        return {"error": None, "data": data}

    @staticmethod
    async def get_list(request: web.Request):
        return [{"x": 3, "y": "3"}] * 3

    @staticmethod
    async def get_attobj(request: web.Request):
        return Data(3, "3")

    @staticmethod
    async def get_string(request: web.Request):
        return "foo"

    @staticmethod
    async def get_number(request: web.Request):
        return 3

    @staticmethod
    async def get_mixed(request: web.Request):
        data = [{"x": 3, "y": "3", "z": [Data(3, "3")] * 2}] * 3
        return data

    @classmethod
    def get(cls, suffix, process=True):
        handlers = cls()
        coro = getattr(handlers, "get_" + suffix)
        loop = asyncio.get_event_loop()
        data = loop.run_until_complete(coro(None))

        return json.loads(json.dumps(data, cls=DataEncoder)) if process else data
