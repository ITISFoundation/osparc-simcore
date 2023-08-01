import functools
from enum import Enum, unique


@unique
class ServiceBootType(str, Enum):
    V0 = "V0"
    V2 = "V2"


@functools.total_ordering
@unique
class ServiceState(Enum):
    PENDING = "pending"
    PULLING = "pulling"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    STOPPING = "stopping"

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            comparison_order = ServiceState.comparison_order()
            self_index = comparison_order[self]
            other_index = comparison_order[other]
            return self_index < other_index
        return NotImplemented

    @staticmethod
    @functools.lru_cache(maxsize=2)
    def comparison_order() -> dict["ServiceState", int]:
        """States are comparable to supportmin() on a list of ServiceState"""
        return {
            ServiceState.FAILED: 0,
            ServiceState.PENDING: 1,
            ServiceState.PULLING: 2,
            ServiceState.STARTING: 3,
            ServiceState.RUNNING: 4,
            ServiceState.STOPPING: 5,
            ServiceState.COMPLETE: 6,
        }
