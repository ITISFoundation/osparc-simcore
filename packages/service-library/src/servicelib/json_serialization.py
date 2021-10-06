import json
from typing import Any
from uuid import UUID


class _UuidEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, UUID):
            # NOTE: careful here!
            return str(o)
        return json.JSONEncoder.default(self, o)


def json_dumps(obj: Any, **kwargs):
    """json.dumps with UUID encoder"""
    return json.dumps(obj, cls=_UuidEncoder, **kwargs)
