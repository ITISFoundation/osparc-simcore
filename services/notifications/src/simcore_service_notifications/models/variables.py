from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import SkipJsonSchema


class BaseContextModel(BaseModel):
    product: SkipJsonSchema[dict[str, Any]]
