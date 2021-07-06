from abc import ABC, abstractmethod

from fastapi import FastAPI

from ....models.schemas.dynamic_services import MonitorData


class MonitorEvent(ABC):
    @classmethod
    @abstractmethod
    async def will_trigger(cls, app: FastAPI, monitor_data: MonitorData) -> bool:
        """
        When returning True the event will trigger and the action
        code will be executed
        """

    @classmethod
    @abstractmethod
    async def action(cls, app: FastAPI, monitor_data: MonitorData) -> None:
        """
        User defined code for this specific event.
        All updates to the status(MonitorData) should be applied to the current variable
        """
