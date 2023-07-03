from datetime import datetime
from typing import Any

from arrow import Arrow
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import BaseModel

# Scraped from prometheus


class ContainerScrapedResourceUsageMetric(BaseModel):
    container_id: str
    image: str
    user_id: UserID
    user_email: str | None
    product_name: ProductName
    project_uuid: ProjectID
    project_name: str | None
    node_uuid: NodeID
    node_label: str | None
    instance: str | None
    service_settings_reservation_nano_cpus: int | None
    service_settings_reservation_memory_bytes: int | None
    service_settings_reservation_additional_info: dict[str, Any] = {}
    service_settings_limit_nano_cpus: int | None
    service_settings_limit_memory_bytes: int | None
    service_key: ServiceKey
    service_version: ServiceVersion


class ContainerScrapedResourceUsageValues(BaseModel):
    container_cpu_usage_seconds_total: float
    prometheus_created: Arrow
    prometheus_last_scraped: Arrow

    class Config:
        arbitrary_types_allowed = True


class ContainerScrapedResourceUsage(
    ContainerScrapedResourceUsageMetric, ContainerScrapedResourceUsageValues
):
    ...


# List containers from DB table


class ContainerGetDB(BaseModel):
    service_settings_reservation_nano_cpus: int | None
    service_settings_reservation_memory_bytes: int | None
    prometheus_created: datetime
    prometheus_last_scraped: datetime
    project_uuid: ProjectID
    project_name: str | None
    node_uuid: NodeID
    node_label: str | None
    service_key: ServiceKey
    service_version: ServiceVersion
