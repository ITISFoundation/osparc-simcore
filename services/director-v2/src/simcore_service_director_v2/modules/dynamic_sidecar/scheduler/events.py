from typing import List, Type

from .abc import DynamicSchedulerEvent

REGISTERED_EVENTS: List[Type[DynamicSchedulerEvent]] = []
