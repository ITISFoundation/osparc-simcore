from abc import abstractclassmethod

from aiohttp.web import Application

from .models import MonitorData


class BaseEventHandler:
    @abstractclassmethod
    async def will_trigger(self, previous: MonitorData, current: MonitorData) -> bool:
        """returns True it the action needs to be invoked"""

    @abstractclassmethod
    async def action(
        self, app: Application, previous: MonitorData, current: MonitorData
    ) -> None:
        """
        Code applied if the handler triggered.
        All updates to the status(MonitorData) should be applied to the current variable
        """

    @classmethod
    async def process(
        self, app: Application, previous: MonitorData, current: MonitorData
    ) -> None:
        """checks and runs the handler if needed"""
        if await self.will_trigger(previous, current):
            await self.action(app, previous, current)
