from fastapi import FastAPI

from ._core import get_core
from ._models import (
    OperationContext,
    OperationName,
    ScheduleId,
    StepName,
)


async def start_operation(
    app: FastAPI,
    operation_name: OperationName,
    initial_operation_context: OperationContext,
) -> ScheduleId:
    return await get_core(app).start_operation(
        operation_name, initial_operation_context
    )


async def cancel_operation(app: FastAPI, schedule_id: ScheduleId) -> None:
    """
    Unstruct scheduler to revert all steps completed until
    now for the running operation.

    `reverting` refers to the act of undoing the effects of a step
    that has already been completed (eg: remove a created network)
    """
    await get_core(app).cancel_operation(schedule_id)


async def restart_operation_step_stuck_in_manual_intervention_during_create(
    app: FastAPI, schedule_id: ScheduleId, step_name: StepName
) -> None:
    """
    restarts a step waiting for manual intervention
    NOTE: to be used only with steps where `wait_for_manual_intervention()` is True

    `waiting for manual intervention` refers to a step that has failed and exhausted
    all retries and is now waiting for a human to fix the issue (eg: storage service
    is reachable once again)
    """
    await get_core(app).restart_operation_step_stuck_in_error(
        schedule_id, step_name, in_manual_intervention=True
    )


async def restart_operation_step_stuck_during_revert(
    app: FastAPI, schedule_id: ScheduleId, step_name: StepName
) -> None:
    """
    Restarts a `stuck step` while the operation is being reverted

    `stuck step` is a step that has failed and exhausted all retries
    `reverting` refers to the act of undoing the effects of a step
    that has already been completed (eg: remove a created network)
    """
    await get_core(app).restart_operation_step_stuck_in_error(
        schedule_id, step_name, in_manual_intervention=False
    )
