from typing import Any

from arrow import Arrow
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import BaseModel


class ContainerResourceUsageMetric(BaseModel):
    container_id: str
    image: str
    user_id: UserID
    product_name: ProductName
    project_uuid: ProjectID
    service_settings_reservation_nano_cpus: int | None
    service_settings_reservation_memory_bytes: int | None
    service_settings_reservation_additional_info: dict[str, Any] = {}


class ContainerResourceUsageValues(BaseModel):
    container_cpu_usage_seconds_total: float
    prometheus_created: Arrow
    prometheus_last_scraped: Arrow

    class Config:
        arbitrary_types_allowed = True


class ContainerResourceUsage(
    ContainerResourceUsageMetric, ContainerResourceUsageValues
):
    ...
