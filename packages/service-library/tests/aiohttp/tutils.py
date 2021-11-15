# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import
# pylint: disable=no-self-use

import asyncio
import json
from dataclasses import dataclass

from aiohttp import web
from servicelib.json_serialization import json_dumps


@dataclass
class Data:
    x: int = 3
    y: str = "foo"


class Handlers:
    async def get_health_wrong(self, request: web.Request):
        out = {
            "name": __name__.split(".")[0],
            "version": "1.0",
            "status": "SERVICE_RUNNING",
            "invalid_entry": 125,
        }
        return out

    async def get_health(self, request: web.Request):
        out = {
            "name": __name__.split(".")[0],
            "version": "1.0",
            "status": "SERVICE_RUNNING",
            "api_version": "1.0",
        }
        return out

    async def get_dict(self, request: web.Request):
        return {"x": 3, "y": "3"}

    async def get_envelope(self, request: web.Request):
        data = {"x": 3, "y": "3"}
        return {"error": None, "data": data}

    async def get_list(self, request: web.Request):
        return [{"x": 3, "y": "3"}] * 3

    async def get_attobj(self, request: web.Request):
        return Data(3, "3")

    async def get_string(self, request: web.Request):
        return "foo"

    async def get_number(self, request: web.Request):
        return 3

    async def get_mixed(self, request: web.Request):
        data = [{"x": 3, "y": "3", "z": [Data(3, "3")] * 2}] * 3
        return data

    @classmethod
    def get(cls, suffix, process=True):
        handlers = cls()
        coro = getattr(handlers, "get_" + suffix)
        loop = asyncio.get_event_loop()
        data = loop.run_until_complete(coro(None))

        return json.loads(json_dumps(data)) if process else data
