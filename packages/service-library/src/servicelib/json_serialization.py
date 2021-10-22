import json
from typing import Any

from pydantic.json import pydantic_encoder


def json_dumps(obj: Any, **kwargs):
    """json.dumps with rich encoder.
    A big applause for pydantic authors here!!!
    """
    return json.dumps(obj, default=pydantic_encoder, **kwargs)


# TODO: support for orjson
# TODO: support for ujson (fast but poor encoding, only for basic types)
