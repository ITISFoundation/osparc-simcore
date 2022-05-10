from typing import Any

from pydantic import BaseModel


class ServiceSpecifications(BaseModel):
    schedule_specs: dict[str, Any]


class ServiceSpecificationsGet(ServiceSpecifications):
    ...
