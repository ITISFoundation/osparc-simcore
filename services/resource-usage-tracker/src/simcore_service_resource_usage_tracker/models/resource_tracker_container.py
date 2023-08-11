from datetime import datetime
from typing import Any, NamedTuple

from arrow import Arrow
from models_library.api_schemas_webserver.resource_usage import ContainerGet
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import BaseModel, ByteSize, Field, PositiveInt
from simcore_postgres_database.models.resource_tracker_containers import (
    ContainerClassification,
)

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
    instance: str | None = Field(
        None,
        description="Instance label scraped via Prometheus (taken from container labels, ex.: gpu1)",
    )
    service_settings_reservation_additional_info: dict[str, Any] = Field(
        {},
        description="Storing additional information about the reservation settings, such as what type of graphic card is used.",
    )
    memory_limit: ByteSize = Field(
        None,
        description="Memory bytes limit set by the runtime, ex. 17179869184 means that the container has limit for 16GB of memory",
    )
    cpu_limit: float = Field(
        None,
        description="CPU limit set by the runtime, ex. 3.5 Shares of one CPU cores",
    )
    service_key: ServiceKey
    service_version: ServiceVersion


class ContainerScrapedResourceUsageValues(BaseModel):
    container_cpu_usage_seconds_total: float
    prometheus_created: Arrow
    prometheus_last_scraped: Arrow

    class Config:
        arbitrary_types_allowed = True


class ContainerScrapedResourceUsageCustom(BaseModel):
    classification: ContainerClassification


class ContainerScrapedResourceUsage(
    ContainerScrapedResourceUsageMetric,
    ContainerScrapedResourceUsageValues,
    ContainerScrapedResourceUsageCustom,
):
    ...


# List containers from DB table


class ContainerGetDB(BaseModel):
    cpu_limit: float
    memory_limit: int
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
