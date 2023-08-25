import enum
from typing import TypeAlias

from pydantic import PositiveInt

ServiceRunId: TypeAlias = str
PricingPlanId: TypeAlias = PositiveInt
PricingDetailId: TypeAlias = PositiveInt


class ResourceTrackerServiceType(str, enum.Enum):
    COMPUTATIONAL_SERVICE = "COMPUTATIONAL_SERVICE"
    DYNAMIC_SERVICE = "DYNAMIC_SERVICE"


class ServiceRunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
