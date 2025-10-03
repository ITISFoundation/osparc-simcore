from typing import TYPE_CHECKING

from fastapi import FastAPI

from ._models import OperationContext, OperationName, ScheduleId

if TYPE_CHECKING:
    from ._event_scheduler import EventScheduler


def _get_event_scheduler(app: FastAPI) -> "EventScheduler":
    # NOTE: could not use EventScheduler.get_from_app_state(app)
    # due to circular dependency
    event_scheduler: EventScheduler = app.state.generic_scheduler_event_scheduler
    return event_scheduler


async def enqueue_schedule_event(app: FastAPI, schedule_id: ScheduleId) -> None:
    await _get_event_scheduler(app).enqueue_schedule_event(schedule_id)


async def enqueue_create_completed_event(
    app: FastAPI,
    schedule_id: ScheduleId,
    operation_name: OperationName,
    initial_context: OperationContext,
) -> None:
    await _get_event_scheduler(app).enqueue_create_completed_event(
        schedule_id, operation_name, initial_context
    )


async def enqueue_undo_completed_event(
    app: FastAPI,
    schedule_id: ScheduleId,
    operation_name: OperationName,
    initial_context: OperationContext,
) -> None:
    await _get_event_scheduler(app).enqueue_undo_completed_event(
        schedule_id, operation_name, initial_context
    )
