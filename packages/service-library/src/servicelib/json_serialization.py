import json
from typing import Any
from uuid import UUID

import ujson


class _UuidEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, UUID):
            # if the obj is uuid, we simply return the value of uuid
            return o.hex
        return json.JSONEncoder.default(self, o)


def json_dumps(obj: Any, **kwargs):
    """json.dumps with UUID encoder"""
    return json.dumps(obj, cls=_UuidEncoder, **kwargs)


def json_dumps_hybrid(obj: Any, **common_kwags):
    try:
        # Fast does not support custom encoders
        # SEE https://github.com/ultrajson/ultrajson/issues/124
        return ujson.dumps(obj, **common_kwags)
    except TypeError:
        return json.dumps(obj, cls=_UuidEncoder, **common_kwags)
