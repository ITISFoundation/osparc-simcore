from abc import ABC, abstractmethod

from fastapi import FastAPI

from ....models.schemas.dynamic_services import SchedulerData


class DynamicSchedulerEvent(ABC):
    @classmethod
    @abstractmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        """
        When returning True the event will trigger and the action
        code will be executed
        """

    @classmethod
    @abstractmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        """
        User defined code for this specific event.
        All updates to the status(SchedulerData) should be applied to the current variable
        """
