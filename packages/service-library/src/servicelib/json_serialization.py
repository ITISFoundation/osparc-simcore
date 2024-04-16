import json
from collections.abc import Callable
from typing import Any

import orjson
from pydantic.json import pydantic_encoder


def json_dumps(obj: Any, **kwargs):
    """json.dumps including a rich encoder (e.g. supports UUID objs)
    A big applause for pydantic authors here!!!
    """
    return json.dumps(obj, default=pydantic_encoder, **kwargs)


class OrJsonAdapter:
    """
    Adapts orjson to have the same interface as json.dumps and json.loads
    """

    @staticmethod
    def dumps(v, *, default: Callable[[Any], Any] | None = None) -> str:
        # SEE https://github.com/ijl/orjson
        # - orjson.dumps returns *bytes*, to match standard json.dumps we need to decode
        decoded: str = orjson.dumps(v, default=default).decode()
        return decoded

    loads = orjson.loads
