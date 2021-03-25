import json
from datetime import datetime
from typing import Dict

import orjson


def _jsoncoverter(obj):
    if isinstance(obj, datetime):
        return obj.__str__()
    if isinstance(obj, bytes):
        return str(obj)
    return obj


def json_dumps_old(obj: Dict) -> str:
    return json.dumps(obj, indent=2, default=_jsoncoverter)


def json_dumps(v, *, default=None) -> str:
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    return orjson.dumps(v, default=default).decode()
