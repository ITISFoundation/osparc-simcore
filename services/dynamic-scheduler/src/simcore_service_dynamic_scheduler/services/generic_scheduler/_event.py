from fastapi import FastAPI

from ._dependencies import get_event_scheduler
from ._event_base_queue import OperationToStartEvent
from ._event_queues import ExecuteCompletedQueue, RevertCompletedQueue, ScheduleQueue
from ._models import OperationToStart, ScheduleId


async def enqueue_schedule_event(app: FastAPI, schedule_id: ScheduleId) -> None:
    await get_event_scheduler(app).enqueue_message_for(ScheduleQueue, schedule_id)


async def enqueue_execute_completed_event(
    app: FastAPI,
    schedule_id: ScheduleId,
    to_start: OperationToStart,
    *,
    on_execute_completed: OperationToStart | None = None,
    on_revert_completed: OperationToStart | None = None,
) -> None:
    await get_event_scheduler(app).enqueue_message_for(
        ExecuteCompletedQueue,
        OperationToStartEvent(
            schedule_id=schedule_id,
            to_start=to_start,
            on_execute_completed=on_execute_completed,
            on_revert_completed=on_revert_completed,
        ),
    )


async def enqueue_revert_completed_event(
    app: FastAPI,
    schedule_id: ScheduleId,
    to_start: OperationToStart,
    *,
    on_execute_completed: OperationToStart | None = None,
    on_revert_completed: OperationToStart | None = None,
) -> None:
    await get_event_scheduler(app).enqueue_message_for(
        RevertCompletedQueue,
        OperationToStartEvent(
            schedule_id=schedule_id,
            to_start=to_start,
            on_execute_completed=on_execute_completed,
            on_revert_completed=on_revert_completed,
        ),
    )
