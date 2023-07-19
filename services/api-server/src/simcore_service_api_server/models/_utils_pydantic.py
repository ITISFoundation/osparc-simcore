from pydantic import Field

from ..utils.serialization import json_dumps, json_loads


class BaseConfig:
    json_loads = json_loads
    json_dumps = json_dumps


NOT_REQUIRED = Field(default=None)
