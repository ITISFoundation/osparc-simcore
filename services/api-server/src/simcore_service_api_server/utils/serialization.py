import json
from collections.abc import Callable
from typing import Any

import orjson


def json_dumps(
    v, *, default: Callable[[Any], Any] | None = None, indent: int | None = None
) -> str:
    # SEE https://github.com/ijl/orjson
    # - orjson.dumps returns *bytes*, to match standard json.dumps we need to decode

    # Cannot use anymore human readable prints like ``print(model.json(indent=2))``
    # because it does not include indent option. This is very convenient for debugging
    # so if added, it switches to json
    if indent:
        return json.dumps(v, default=default, indent=indent)

    decoded: str = orjson.dumps(v, default=default).decode()
    return decoded


json_loads = orjson.loads
