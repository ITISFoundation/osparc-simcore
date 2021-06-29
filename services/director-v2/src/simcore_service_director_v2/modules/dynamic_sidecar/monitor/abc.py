from abc import ABC, abstractclassmethod

from fastapi import FastAPI

from .models import MonitorData


class MonitorEvent(ABC):
    @abstractclassmethod
    async def will_trigger(cls, app: FastAPI, monitor_data: MonitorData) -> bool:
        """
        When returning True the event will trigger and the action
        code will be executed
        """

    @abstractclassmethod
    async def action(cls, app: FastAPI, monitor_data: MonitorData) -> None:
        """
        User defined code for this specific event.
        All updates to the status(MonitorData) should be applied to the current variable
        """
