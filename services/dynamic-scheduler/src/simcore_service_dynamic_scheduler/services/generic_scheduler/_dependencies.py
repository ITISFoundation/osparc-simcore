from typing import TYPE_CHECKING

from fastapi import FastAPI

from ._models import ScheduleId

if TYPE_CHECKING:
    from ._event_scheduler import EventScheduler


async def enqueue_event(app: FastAPI, schedule_id: ScheduleId) -> None:
    event_scheduler: EventScheduler = app.state.generic_scheduler_event_scheduler
    await event_scheduler.enqueue_event(schedule_id)
