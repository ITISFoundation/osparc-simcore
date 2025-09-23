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
    """starts an operation by it's given name and initial context"""
    return await get_core(app).start_operation(
        operation_name, initial_operation_context
    )


async def cancel_operation(app: FastAPI, schedule_id: ScheduleId) -> None:
    """puts an operation to revert from the point it currently is"""
    await get_core(app).cancel_operation(schedule_id)


async def restart_operation_stuck_in_manual_intervention_during_create(
    app: FastAPI, schedule_id: ScheduleId, step_name: StepName
) -> None:
    """
    restarts a step waiting for manual intervention
    NOTE: to be used only with steps where `wait_for_manual_intervention()` is True
    """
    await get_core(app).restart_operation_step_stuck_in_error(
        schedule_id, step_name, in_manual_intervention=True
    )


async def restart_operation_stuck_in_error_during_revert(
    app: FastAPI, schedule_id: ScheduleId, step_name: StepName
) -> None:
    """restarts a step stuck in `revert` in an error state"""
    await get_core(app).restart_operation_step_stuck_in_error(
        schedule_id, step_name, in_manual_intervention=False
    )
