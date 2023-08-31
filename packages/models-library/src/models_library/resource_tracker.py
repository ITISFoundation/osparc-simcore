from enum import auto
from typing import TypeAlias

from pydantic import PositiveInt

from .utils.enums import StrAutoEnum

ServiceRunId: TypeAlias = str
PricingPlanId: TypeAlias = PositiveInt
PricingDetailId: TypeAlias = PositiveInt


class ResourceTrackerServiceType(StrAutoEnum):
    COMPUTATIONAL_SERVICE = auto()
    DYNAMIC_SERVICE = auto()


class ServiceRunStatus(StrAutoEnum):
    RUNNING = auto()
    SUCCESS = auto()
    ERROR = auto()
