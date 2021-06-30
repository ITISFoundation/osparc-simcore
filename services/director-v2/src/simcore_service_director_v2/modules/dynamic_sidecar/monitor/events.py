from typing import List, Type

from .abc import MonitorEvent

REGISTERED_EVENTS: List[Type[MonitorEvent]] = []
