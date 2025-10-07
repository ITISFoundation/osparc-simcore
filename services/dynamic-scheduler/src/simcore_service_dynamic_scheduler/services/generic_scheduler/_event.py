from fastapi import FastAPI

from ._dependencies import get_event_scheduler
from ._event_base_queue import OperationToStartEvent
from ._event_queues import CreateCompletedQueue, ScheduleQueue, UndoCompletedQueue
from ._models import OperationContext, OperationName, ScheduleId


async def enqueue_schedule_event(app: FastAPI, schedule_id: ScheduleId) -> None:
    await get_event_scheduler(app).enqueue_message_for(ScheduleQueue, schedule_id)


async def enqueue_create_completed_event(
    app: FastAPI,
    schedule_id: ScheduleId,
    operation_name: OperationName,
    initial_context: OperationContext,
) -> None:
    await get_event_scheduler(app).enqueue_message_for(
        CreateCompletedQueue,
        OperationToStartEvent(
            schedule_id=schedule_id,
            operation_name=operation_name,
            initial_context=initial_context,
        ),
    )


async def enqueue_undo_completed_event(
    app: FastAPI,
    schedule_id: ScheduleId,
    operation_name: OperationName,
    initial_context: OperationContext,
) -> None:
    await get_event_scheduler(app).enqueue_message_for(
        UndoCompletedQueue,
        OperationToStartEvent(
            schedule_id=schedule_id,
            operation_name=operation_name,
            initial_context=initial_context,
        ),
    )
