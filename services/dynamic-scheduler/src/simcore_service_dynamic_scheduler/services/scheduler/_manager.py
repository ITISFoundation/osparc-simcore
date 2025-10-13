import logging
from datetime import timedelta
from typing import Final

from fastapi import FastAPI
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.projects_nodes_io import NodeID
from pydantic import NonNegativeFloat
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

from ..generic_scheduler import (
    NoDataFoundError,
    OperationToStart,
    ScheduleId,
    cancel_operation,
    get_operation_name_or_none,
    register_to_start_after_on_executed_completed,
    register_to_start_after_on_reverted_completed,
    start_operation,
)
from . import _opration_names
from ._errors import (
    UnexpectedCouldNotFindCurrentScheduledIdError,
    UnexpectedCouldNotFindOperationNameError,
)
from ._models import DesiredState, OperationType
from ._redis import RedisServiceStateManager
from ._utils import get_scheduler_operation_type_or_raise

_logger = logging.getLogger(__name__)

_MAX_WAIT_TIME_FOR_SCHEDULE_ID: Final[NonNegativeFloat] = timedelta(
    seconds=5
).total_seconds()


async def _get_schedule_id_and_opration_type(
    app: FastAPI, service_state_manager: RedisServiceStateManager
) -> tuple[ScheduleId, OperationType]:

    # NOTE: current_schedule_id is expected to be None,
    # while oprations are switching.
    # Waiting a very short time should usually fix the issue.
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(_MAX_WAIT_TIME_FOR_SCHEDULE_ID),
        reraise=True,
        retry=retry_if_exception_type(UnexpectedCouldNotFindOperationNameError),
    ):
        with attempt:
            current_schedule_id = await service_state_manager.read(
                "current_schedule_id"
            )
            if current_schedule_id is None:
                raise UnexpectedCouldNotFindCurrentScheduledIdError

    assert current_schedule_id is not None  # nosec

    opration_name = await get_operation_name_or_none(app, current_schedule_id)
    if opration_name is None:
        raise UnexpectedCouldNotFindOperationNameError(schedule_id=current_schedule_id)

    operation_type = get_scheduler_operation_type_or_raise(name=opration_name)

    return current_schedule_id, operation_type


async def _switch_to_enforce(
    app: FastAPI, schedule_id: ScheduleId, node_id: NodeID
) -> None:
    try:
        enforce_operation = OperationToStart(
            _opration_names.ENFORCE, {"node_id": node_id}
        )
        await register_to_start_after_on_executed_completed(
            app, schedule_id, to_start=enforce_operation
        )
        await register_to_start_after_on_reverted_completed(
            app, schedule_id, to_start=enforce_operation
        )
        await cancel_operation(app, schedule_id)
    except NoDataFoundError:
        _logger.debug("Could not switch schedule_id='%s' to ENFORCE.", schedule_id)


async def start_service(app: FastAPI, start_data: DynamicServiceStart) -> None:
    node_id = start_data.node_uuid
    service_state_manager = RedisServiceStateManager(app=app, node_id=node_id)

    if not await service_state_manager.exists():
        # no data exists, entrypoint for staring the service
        await service_state_manager.create_or_update_multiple(
            {
                "desired_state": DesiredState.RUNNING,
                "desired_start_data": start_data,
            }
        )
        enforce_operation = OperationToStart(
            _opration_names.ENFORCE, {"node_id": node_id}
        )
        await start_operation(
            app,
            _opration_names.ENFORCE,
            {"node_id": node_id},
            on_execute_completed=enforce_operation,
            on_revert_completed=enforce_operation,
        )
        _logger.debug("node_di='%s' added to tracking", node_id)
        return

    current_schedule_id, operation_type = await _get_schedule_id_and_opration_type(
        app, service_state_manager
    )

    match operation_type:
        # NOTE: STOP opreration cannot be cancelled
        case OperationType.ENFORCE | OperationType.START:
            if await service_state_manager.read("current_start_data") != start_data:
                await _switch_to_enforce(app, current_schedule_id, node_id)
        case OperationType.MONITOR:
            await _switch_to_enforce(app, current_schedule_id, node_id)

    # set as current
    await service_state_manager.create_or_update("current_start_data", start_data)


async def stop_service(app: FastAPI, stop_data: DynamicServiceStop) -> None:
    node_id = stop_data.node_id
    service_state_manager = RedisServiceStateManager(app=app, node_id=node_id)

    if not await service_state_manager.exists():
        # it is always possible to schedule the service for a stop,
        # primary use case is platform cleanup
        await service_state_manager.create_or_update_multiple(
            {
                "desired_state": DesiredState.STOPPED,
                "desired_stop_data": stop_data,
            }
        )
        enforce_operation = OperationToStart(
            _opration_names.ENFORCE, {"node_id": node_id}
        )
        await start_operation(
            app,
            _opration_names.ENFORCE,
            {"node_id": node_id},
            on_execute_completed=enforce_operation,
            on_revert_completed=enforce_operation,
        )
        return

    current_schedule_id, operation_type = await _get_schedule_id_and_opration_type(
        app, service_state_manager
    )

    match operation_type:
        # NOTE: STOP opreration cannot be cancelled
        case OperationType.ENFORCE:
            if await service_state_manager.read("current_stop_data") != stop_data:
                await _switch_to_enforce(app, current_schedule_id, node_id)
        case OperationType.START | OperationType.MONITOR:
            await _switch_to_enforce(app, current_schedule_id, node_id)

    # set as current
    await service_state_manager.create_or_update("current_stop_data", stop_data)
