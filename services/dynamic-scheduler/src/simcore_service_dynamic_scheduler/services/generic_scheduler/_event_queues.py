from ._dependencies import get_after_event_manager, get_core
from ._event_base_queue import BaseEventQueue, OperationToStartEvent
from ._models import EventType, ScheduleId


class ScheduleQueue(BaseEventQueue):
    async def handler(  # type:ignore[override] # pylint:disable=arguments-differ
        self, schedule_id: ScheduleId
    ) -> None:
        await get_core(self.app).safe_on_schedule_event(schedule_id)


class ExecuteCompletedQueue(BaseEventQueue):
    async def handler(  # type:ignore[override] # pylint:disable=arguments-differ
        self, event: OperationToStartEvent
    ) -> None:
        await get_after_event_manager(self.app).safe_on_event_type(
            EventType.ON_EXECUTED_COMPLETED,
            event.schedule_id,
            event.to_start,
            on_execute_completed=event.on_execute_completed,
            on_revert_completed=event.on_revert_completed,
        )


class RevertCompletedQueue(BaseEventQueue):
    async def handler(  # type:ignore[override] # pylint:disable=arguments-differ
        self, event: OperationToStartEvent
    ) -> None:
        await get_after_event_manager(self.app).safe_on_event_type(
            EventType.ON_REVERT_COMPLETED,
            event.schedule_id,
            event.to_start,
            on_execute_completed=event.on_execute_completed,
            on_revert_completed=event.on_revert_completed,
        )
