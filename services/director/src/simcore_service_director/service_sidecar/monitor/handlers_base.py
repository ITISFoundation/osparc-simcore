from abc import abstractclassmethod
from .models import MonitorData


class BaseEventHandler:
    @abstractclassmethod
    async def will_trigger(self, previous: MonitorData, current: MonitorData) -> bool:
        """returns True it the action needs to be invoked"""

    @abstractclassmethod
    async def action(self, previous: MonitorData, current: MonitorData) -> None:
        """code need to be run when this the condition is met"""

    async def process(self, previous: MonitorData, current: MonitorData) -> None:
        """checks and runs the handler if needed"""
        if await self.will_trigger(previous, current):
            await self.action(previous, current)



