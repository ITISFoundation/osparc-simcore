import json
from typing import Any, Callable, Optional

import orjson


def json_dumps(
    v, *, default: Optional[Callable[[Any], Any]] = None, indent: Optional[int] = None
) -> str:
    # SEE https://github.com/ijl/orjson
    # - orjson.dumps returns *bytes*, to match standard json.dumps we need to decode

    # Cannot use anymore human readable prints like ``print(model.json(indent=2))``
    # because it does not include indent option. This is very convenient for debugging
    # so if added, it switches to json
    if indent:
        return json.dumps(v, default=default, indent=indent)

    return orjson.dumps(v, default=default).decode()


json_loads = orjson.loads
