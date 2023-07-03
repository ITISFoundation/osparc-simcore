from datetime import datetime
from typing import Any, NamedTuple

from arrow import Arrow
from models_library.api_schemas_webserver.resource_usage import ContainerGet
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from models_library.utils.pydantic_tools_extension import parse_obj_or_none
from pydantic import BaseModel, PositiveInt, validator

# Scraped from prometheus


class ContainerScrapedResourceUsageMetric(BaseModel):
    container_id: str
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

    @validator("service_settings_reservation_nano_cpus", pre=True)
    @classmethod
    def service_settings_reservation_nano_cpus_to_object_or_none(cls, v):
        return parse_obj_or_none(int, v)

    @validator("service_settings_reservation_memory_bytes", pre=True)
    @classmethod
    def service_settings_reservation_memory_bytes_to_object_or_none(cls, v):
        return parse_obj_or_none(int, v)

    @validator("service_settings_limit_nano_cpus", pre=True)
    @classmethod
    def fservice_settings_limit_nano_cpus_to_object(cls, v):
        return parse_obj_or_none(int, v)

    @validator("service_settings_limit_memory_bytes", pre=True)
    @classmethod
    def service_settings_limit_memory_bytes_to_object_or_none(cls, v):
        return parse_obj_or_none(int, v)


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


class ContainersPage(NamedTuple):
    items: list[ContainerGet]
    total: PositiveInt
