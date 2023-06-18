from arrow import Arrow
from models_library.users import UserID
from pydantic import BaseModel


class ContainerResourceUsageMetric(BaseModel):
    container_id: str
    image: str
    user_id: UserID
    product_name: str
    cpu_reservation: int | None
    ram_reservation: int | None


class ContainerResourceUsageValues(BaseModel):
    container_cpu_usage_seconds_total: float
    created_timestamp: Arrow
    last_prometheus_scraped_timestamp: Arrow

    class Config:
        arbitrary_types_allowed = True


class ContainerResourceUsage(
    ContainerResourceUsageMetric, ContainerResourceUsageValues
):
    ...
