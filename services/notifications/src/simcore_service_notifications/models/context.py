from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import SkipJsonSchema


class NotificationsContext(BaseModel):
    product: SkipJsonSchema[dict[str, Any]]
