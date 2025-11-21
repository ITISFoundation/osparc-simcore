from fastapi import FastAPI

from ._dependencies import get_event_scheduler
from ._event_base_queue import OperationToStartEvent
from ._event_queues import ExecuteCompletedQueue, RevertCompletedQueue, ScheduleQueue
from ._models import OperationContext, OperationName, ScheduleId


async def enqueue_schedule_event(app: FastAPI, schedule_id: ScheduleId) -> None:
    await get_event_scheduler(app).enqueue_message_for(ScheduleQueue, schedule_id)


async def enqueue_execute_completed_event(
    app: FastAPI,
    schedule_id: ScheduleId,
    operation_name: OperationName,
    initial_context: OperationContext,
) -> None:
    await get_event_scheduler(app).enqueue_message_for(
        ExecuteCompletedQueue,
        OperationToStartEvent(
            schedule_id=schedule_id,
            operation_name=operation_name,
            initial_context=initial_context,
        ),
    )


async def enqueue_revert_completed_event(
    app: FastAPI,
    schedule_id: ScheduleId,
    operation_name: OperationName,
    initial_context: OperationContext,
) -> None:
    await get_event_scheduler(app).enqueue_message_for(
        RevertCompletedQueue,
        OperationToStartEvent(
            schedule_id=schedule_id,
            operation_name=operation_name,
            initial_context=initial_context,
        ),
    )
