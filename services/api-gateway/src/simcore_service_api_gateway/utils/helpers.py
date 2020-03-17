from typing import Dict
import json
from datetime import datetime

# CAST
def to_bool(s: str) -> bool:
    return s.lower() in ["true", "1", "yes"]


def jsoncoverter(obj):
    if isinstance(obj, datetime):
        return obj.__str__()
    if isinstance(obj, bytes):
        return str(obj)
    return obj


def json_dumps(obj: Dict) -> str:
    return json.dumps(obj, indent=2, default=jsoncoverter)
