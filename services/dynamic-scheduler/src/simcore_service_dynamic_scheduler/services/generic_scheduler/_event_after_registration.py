from typing import TYPE_CHECKING

from fastapi import FastAPI

from ._models import EventType, OperationToStart, ScheduleId

if TYPE_CHECKING:
    from ._event_after import AfterEventManager


def _get_after_event_manager(app: FastAPI) -> "AfterEventManager":
    # NOTE: could not use AfterEventManager.get_from_app_state(app)
    # due to circular dependency
    after_event_manager: AfterEventManager = app.state.after_event_manager
    return after_event_manager


async def register_to_start_after_on_executed_completed(
    app: FastAPI,
    schedule_id: ScheduleId,
    *,
    to_start: OperationToStart | None,
    on_execute_completed: OperationToStart | None = None,
    on_revert_completed: OperationToStart | None = None,
) -> None:
    """raises raises NoDataFoundError"""
    await _get_after_event_manager(app).register_to_start_after(
        schedule_id,
        EventType.ON_EXECUTED_COMPLETED,
        to_start=to_start,
        on_execute_completed=on_execute_completed,
        on_revert_completed=on_revert_completed,
    )


async def register_to_start_after_on_reverted_completed(
    app: FastAPI,
    schedule_id: ScheduleId,
    *,
    to_start: OperationToStart | None,
    on_execute_completed: OperationToStart | None = None,
    on_revert_completed: OperationToStart | None = None,
) -> None:
    """raises raises NoDataFoundError"""
    await _get_after_event_manager(app).register_to_start_after(
        schedule_id,
        EventType.ON_REVERT_COMPLETED,
        to_start=to_start,
        on_execute_completed=on_execute_completed,
        on_revert_completed=on_revert_completed,
    )
