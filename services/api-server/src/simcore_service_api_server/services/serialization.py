import json
from datetime import datetime
from typing import Dict


def to_bool(s: str) -> bool:
    return s.lower() in ["true", "1", "yes"]


def _jsoncoverter(obj):
    if isinstance(obj, datetime):
        return obj.__str__()
    if isinstance(obj, bytes):
        return str(obj)
    return obj


def json_dumps(obj: Dict) -> str:
    return json.dumps(obj, indent=2, default=_jsoncoverter)
