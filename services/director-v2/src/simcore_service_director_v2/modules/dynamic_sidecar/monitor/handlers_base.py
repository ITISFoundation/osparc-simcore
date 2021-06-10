from abc import abstractclassmethod

from fastapi import FastAPI

from .models import MonitorData


class MonitorEvent:
    @abstractclassmethod
    async def will_trigger(
        self, app: FastAPI, previous: MonitorData, current: MonitorData
    ) -> bool:
        """
        When returning True the event will trigger and the action
        code will be executed
        """

    @abstractclassmethod
    async def action(
        self, app: FastAPI, previous: MonitorData, current: MonitorData
    ) -> None:
        """
        User defined code for this specific event.
        All updates to the status(MonitorData) should be applied to the current variable
        """
