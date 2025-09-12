import asyncio
import logging
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Final
from uuid import uuid4

from common_library.error_codes import create_error_code
from fastapi import FastAPI
from fastapi_lifespan_manager import State
from pydantic import NonNegativeInt
from servicelib.logging_errors import create_troubleshootting_log_kwargs
from servicelib.logging_utils import log_context
from servicelib.utils import limited_gather

from ._deferred_runner import DeferredRunner
from ._dependencies import enqueue_schedule_event
from ._errors import UnexpectedStepHandlingError
from ._models import (
    OperationContext,
    OperationErrorType,
    OperationName,
    ScheduleId,
    StepName,
    StepStatus,
)
from ._operation import BaseStepGroup, Operation, OperationRegistry
from ._store import (
    KeyNotFoundInHashError,
    ScheduleDataStoreProxy,
    StepGroupProxy,
    StepStoreProxy,
    Store,
    get_store,
)

_PARALLEL_STATUS_REQUESTS: Final[NonNegativeInt] = 5
_DEFAULT_UNKNOWN_STATUS_MAX_RETRY: Final[NonNegativeInt] = 3
_DEFAULT_UNKNOWN_STATUS_WAIT_BEFORE_RETRY: Final[timedelta] = timedelta(seconds=1)

_logger = logging.getLogger(__name__)


_IN_PROGRESS_STATUSES: Final[set[StepStatus]] = {
    StepStatus.SCHEDULED,
    StepStatus.CREATED,
    StepStatus.RUNNING,
}


async def _was_step_started(step_proxy: StepStoreProxy) -> tuple[bool, StepStoreProxy]:
    try:
        was_stated = (await step_proxy.get("deferred_created")) is True
    except KeyNotFoundInHashError:
        was_stated = False

    return was_stated, step_proxy


async def _get_steps_to_start(
    step_proxies: Iterable[StepStoreProxy],
) -> list[StepStoreProxy]:
    result: list[tuple[bool, StepStoreProxy]] = await limited_gather(
        *(_was_step_started(step) for step in step_proxies),
        limit=_PARALLEL_STATUS_REQUESTS,
    )
    return [proxy for was_started, proxy in result if was_started is False]


async def _get_step_status(step_proxy: StepStoreProxy) -> tuple[StepName, StepStatus]:
    try:
        status = await step_proxy.get("status")
    except KeyNotFoundInHashError:
        status = StepStatus.UNKNOWN

    return step_proxy.step_name, status


async def _get_steps_statuses(
    step_proxies: Iterable[StepStoreProxy],
) -> dict[StepName, StepStatus]:
    result: list[tuple[StepName, StepStatus]] = await limited_gather(
        *(_get_step_status(step) for step in step_proxies),
        limit=_PARALLEL_STATUS_REQUESTS,
    )
    return dict(result)


async def _is_operation_in_progress_status(
    steps_statuses: dict[StepName, StepStatus],
) -> bool:
    return any(status in _IN_PROGRESS_STATUSES for status in steps_statuses.values())


async def _start_and_mark_as_started(
    step_proxy: StepStoreProxy,
    *,
    is_creating: bool,
    expected_steps_count: NonNegativeInt,
) -> None:
    await DeferredRunner.start(
        schedule_id=step_proxy.schedule_id,
        operation_name=step_proxy.operation_name,
        step_group_name=step_proxy.step_group_name,
        step_name=step_proxy.step_name,
        is_creating=is_creating,
        expected_steps_count=expected_steps_count,
    )
    await step_proxy.set_multiple(
        {
            "deferred_created": True,
            "status": StepStatus.SCHEDULED,
            "success_processed": False,
        }
    )


class Core:
    def __init__(
        self,
        app: FastAPI,
        unknown_status_max_retry: NonNegativeInt = _DEFAULT_UNKNOWN_STATUS_MAX_RETRY,
        unknown_status_wait_before_retry: timedelta = _DEFAULT_UNKNOWN_STATUS_WAIT_BEFORE_RETRY,
    ) -> None:
        self.app = app
        self.unknown_status_max_retry = unknown_status_max_retry
        self.unknown_status_wait_before_retry = unknown_status_wait_before_retry
        self._store: Store = get_store(app)

        self._debug_counter: int = 0  # TODO: remove this
        self._debug_first_call: datetime | None = None

    async def setup(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def create(
        self, operation_name: OperationName, operation_context: OperationContext
    ) -> ScheduleId:
        """entrypoint for sceduling returns a unique schedule_id"""
        schedule_id: ScheduleId = f"{uuid4()}"

        # check if operation is registerd
        OperationRegistry.get_operation(operation_name)
        schedule_data_proxy = ScheduleDataStoreProxy(
            store=self._store, schedule_id=schedule_id
        )
        await schedule_data_proxy.set_multiple(
            {
                "operation_name": operation_name,
                "operation_context": operation_context,
                "group_index": 0,
                "is_creating": True,
            }
        )
        await enqueue_schedule_event(self.app, schedule_id)
        return schedule_id

    @asynccontextmanager
    async def _safe_event(self, schedule_id: ScheduleId) -> AsyncIterator[None]:
        try:
            yield
        except KeyNotFoundInHashError as err:
            _logger.debug(
                "Cannot process schedule_id='%s' since it's data was not found: %s",
                schedule_id,
                err,
            )
        except Exception as err:  # pylint:disable=broad-exception-caught
            error_code = create_error_code(err)
            log_kwargs = create_troubleshootting_log_kwargs(
                "Unexpected error druing scheduling",
                error=err,
                error_code=error_code,
                error_context={"schedule_id": schedule_id},
                tip="This is a bug, please report it to the developers",
            )
            _logger.exception(**log_kwargs)
            await self._set_unexpected_opration_state(
                schedule_id,
                OperationErrorType.FRAMEWORK_ISSUE,
                message=log_kwargs["msg"],
            )

    async def safe_on_schedule_event(self, schedule_id: ScheduleId) -> None:
        # NOTE: do not call this directly, you are doing something wrong
        async with self._safe_event(schedule_id):
            await self._on_schedule_event(schedule_id)

    async def cancel_schedule(self, schedule_id: ScheduleId) -> None:
        """
        Cancels and runs destruction of the operation
        NOTE: if cancels all steps if is_creating is True or does nothing if is_creating is False
        """
        schedule_data_proxy = ScheduleDataStoreProxy(
            store=self._store, schedule_id=schedule_id
        )

        is_creating = await schedule_data_proxy.get("is_creating")

        if is_creating is False:
            _logger.warning(
                "Cannot cancel steps for schedule_id='%s' since REVERT is running",
                schedule_id,
            )
            return

        operation_name = await schedule_data_proxy.get("operation_name")
        group_index = await schedule_data_proxy.get("group_index")

        operation = OperationRegistry.get_operation(operation_name)
        group = operation[group_index]

        for step in group.get_step_subgroup_to_run():
            step_name = step.get_step_name()
            step_proxy = StepStoreProxy(
                store=self._store,
                schedule_id=schedule_id,
                operation_name=operation_name,
                step_group_name=group.get_step_group_name(index=group_index),
                step_name=step_name,
                is_creating=is_creating,
            )
            with log_context(
                _logger,
                logging.DEBUG,
                f"Cancelling step {step_name=} of operation {operation_name=} for schedule {schedule_id=}",
            ):
                deferred_task_uid = await step_proxy.get("deferred_task_uid")
                await DeferredRunner.cancel(deferred_task_uid)

    async def _get_group_step_proxies(
        self,
        *,
        schedule_id: ScheduleId,
        operation_name: OperationName,
        group_index: NonNegativeInt,
        step_group: BaseStepGroup,
        is_creating: bool,
    ) -> dict[StepName, StepStoreProxy]:
        return {
            step.get_step_name(): StepStoreProxy(
                store=self._store,
                schedule_id=schedule_id,
                operation_name=operation_name,
                step_group_name=step_group.get_step_group_name(index=group_index),
                step_name=step.get_step_name(),
                is_creating=is_creating,
            )
            for step in step_group.get_step_subgroup_to_run()
        }

    def _to_remove_debug_code(self, schedule_id: ScheduleId) -> None:
        # TODO: remove the entide debug code here
        if self._debug_counter == 0:
            self._debug_first_call = datetime.utcnow()

        self._debug_counter += 1
        assert self._debug_first_call is not None  # nosec
        _elapsed = (datetime.utcnow() - self._debug_first_call).total_seconds()
        _logger.debug(
            "Handling event for schedule_id=%s count=%s elapsed=%s, events_per_second=%s",
            schedule_id,
            self._debug_counter,
            _elapsed,
            self._debug_counter / _elapsed,
        )

    async def _on_schedule_event(self, schedule_id: ScheduleId) -> None:
        self._to_remove_debug_code(schedule_id)

        schedule_data_proxy = ScheduleDataStoreProxy(
            store=self._store, schedule_id=schedule_id
        )

        operation_name = await schedule_data_proxy.get("operation_name")
        is_creating = await schedule_data_proxy.get("is_creating")
        group_index = await schedule_data_proxy.get("group_index")

        operation = OperationRegistry.get_operation(operation_name)
        step_group = operation[group_index]

        group_step_proxies = await self._get_group_step_proxies(
            schedule_id=schedule_id,
            operation_name=operation_name,
            group_index=group_index,
            step_group=step_group,
            is_creating=is_creating,
        )
        group_step_count = len(step_group)

        # get steps to start
        if to_start_step_proxies := await _get_steps_to_start(
            group_step_proxies.values()
        ):
            steps_to_start_names = [
                step_proxy.step_name for step_proxy in to_start_step_proxies
            ]
            with log_context(
                _logger,
                logging.DEBUG,
                f"starting steps: {steps_to_start_names=}",
            ):
                await limited_gather(
                    *(
                        _start_and_mark_as_started(
                            step_proxy,
                            is_creating=is_creating,
                            expected_steps_count=group_step_count,
                        )
                        for step_proxy in to_start_step_proxies
                    ),
                    limit=_PARALLEL_STATUS_REQUESTS,
                )
            return

        steps_statuses = await _get_steps_statuses(group_step_proxies.values())
        _logger.debug("DETECTED: steps_statuses=%s", steps_statuses)

        # wait for all steps to finish before continuing
        if await _is_operation_in_progress_status(steps_statuses):
            _logger.debug(
                "Operation '%s' has not finished: steps_statuses='%s'",
                operation_name,
                group_step_proxies,
            )
            return

        # The parallel steps generate multiple events which causes the last step to be processde more than once
        # How do we exlcude this?

        # 6 times for -> Operation completed: steps_statuses={'_AddButter': 'SUCCESS', '_AddSalt': 'SUCCESS', '_AddPepper': 'SUCCESS', '_AddPaprika': 'SUCCESS', '_AddMint': 'SUCCESS', '_AddMilk': 'SUCCESS'}
        # 6 times for -> Operation completed: steps_statuses={'_StirTillDone': 'SUCCESS'}
        _logger.debug("Operation completed: steps_statuses=%s", steps_statuses)

        # NOTE: at this point all steps are in a final status
        if is_creating:
            await self._continue_handling_as_creation(
                steps_statuses,
                schedule_data_proxy,
                schedule_id,
                operation_name,
                group_index,
                step_group,
                operation,
            )
        else:
            await self._continue_handling_as_reverting(
                steps_statuses, schedule_data_proxy, schedule_id, group_index
            )

    async def _continue_handling_as_creation(
        self,
        steps_statuses: dict[StepName, StepStatus],
        schedule_data_proxy: ScheduleDataStoreProxy,
        schedule_id: ScheduleId,
        operation_name: OperationName,
        group_index: NonNegativeInt,
        current_step_group: BaseStepGroup,
        operation: Operation,
    ) -> None:
        # if all in SUUCESS -> move to next
        if all(status == StepStatus.SUCCESS for status in steps_statuses.values()):
            try:
                next_group_index = group_index + 1
                # does a next group exist?
                _ = operation[next_group_index]
                await schedule_data_proxy.set("group_index", value=next_group_index)
                await enqueue_schedule_event(self.app, schedule_id)
            except IndexError:
                # does the step need repeating?
                if current_step_group.repeat_steps is True:
                    _logger.debug(
                        "Operation '%s' for schedule_id='%s' REPEATING step group index %s",
                    )
                    # wait before repeating
                    await asyncio.sleep(
                        current_step_group.wait_before_repeat.total_seconds()
                    )
                    # clear previous run data for each step
                    for step in current_step_group.get_step_subgroup_to_run():
                        step_rproxy = StepStoreProxy(
                            store=self._store,
                            schedule_id=schedule_id,
                            operation_name=operation_name,
                            step_group_name=current_step_group.get_step_group_name(
                                index=group_index
                            ),
                            step_name=step.get_step_name(),
                            is_creating=True,
                        )
                        await step_rproxy.remove()

                    group_proxy = StepGroupProxy(
                        store=self._store,
                        schedule_id=schedule_id,
                        operation_name=operation_name,
                        step_group_name=current_step_group.get_step_group_name(
                            index=group_index
                        ),
                        is_creating=True,
                    )
                    await group_proxy.remove()

                    await enqueue_schedule_event(self.app, schedule_id)
                else:
                    # TODO: the end has bean reached, do nothing from now on
                    _logger.debug(
                        "Operation '%s' for schedule_id='%s' COMPLETED successfully",
                        operation_name,
                        schedule_id,
                    )

            return

        # check if it should wait for manual intervention
        manual_intervention_step_names: set[StepName] = set()
        current_step_group.get_step_subgroup_to_run()
        for step in current_step_group.get_step_subgroup_to_run():
            step_status = steps_statuses.get(step.get_step_name(), None)
            if (
                step_status == StepStatus.FAILED
                and await step.get_create_error_for_manual_intervention()
            ):
                step_proxy = StepStoreProxy(
                    store=self._store,
                    schedule_id=schedule_id,
                    operation_name=operation_name,
                    step_group_name=current_step_group.get_step_group_name(
                        index=group_index
                    ),
                    step_name=step.get_step_name(),
                    is_creating=True,
                )
                await step_proxy.set("requires_manual_intervention", value=True)
                manual_intervention_step_names.add(step.get_step_name())

        if manual_intervention_step_names:
            message = (
                f"Operation '{operation_name}' for schedule_id='{schedule_id}' "
                f"requires manual intervention for steps: {manual_intervention_step_names}"
            )
            _logger.warning(message)
            await self._set_unexpected_opration_state(
                schedule_id, OperationErrorType.STEP_ISSUE, message=message
            )
            return

        # if any in FAILED (no manual intervention) or CANCELLED -> move to revert
        # NOTE:
        # - CANCELLED is expected here and means to go to revert
        # - FAILED unexpected, therw should already be an error entry present in step's store
        if any(
            s in {StepStatus.FAILED, StepStatus.CANCELLED}
            for s in steps_statuses.values()
        ):
            with log_context(
                _logger,
                logging.DEBUG,
                f"{operation_name=} was not successfull: {steps_statuses=}, moving to revert",
            ):
                await schedule_data_proxy.set("is_creating", value=False)
                await enqueue_schedule_event(self.app, schedule_id)
            return

        raise UnexpectedStepHandlingError(
            direction="creation", steps_statuses=steps_statuses, schedule_id=schedule_id
        )

    async def _continue_handling_as_reverting(
        self,
        steps_statuses: dict[StepName, StepStatus],
        schedule_data_proxy: ScheduleDataStoreProxy,
        schedule_id: ScheduleId,
        group_index: NonNegativeInt,
    ) -> None:
        # if all in SUUCESS -> go back to previous untill done
        if all(s == StepStatus.SUCCESS for s in steps_statuses.values()):
            previous_group_index = group_index - 1
            if previous_group_index < 0:
                # no more to revert
                return

            await schedule_data_proxy.set("group_index", value=previous_group_index)
            await enqueue_schedule_event(self.app, schedule_id)
            return

        # if any in FAILED this is unexpected falg to be investigated
        failed_step_names: list[StepName] = [
            n for n, s in steps_statuses.items() if s == StepStatus.FAILED
        ]
        if failed_step_names:
            message = (
                f"Operation 'revert' for schedule_id='{schedule_id}' failed for steps: "
                f"{failed_step_names}. Step code should never fail during destruction, "
                "please report to developers."
            )
            _logger.error(message)
            await self._set_unexpected_opration_state(
                schedule_id, OperationErrorType.STEP_ISSUE, message=message
            )
            return

        # if any CANCELLD: this is unexpected falg to be investigated
        cancelled_step_names: list[StepName] = [
            n for n, s in steps_statuses.items() if s == StepStatus.CANCELLED
        ]
        if cancelled_step_names:
            message = (
                f"Operation 'revert' for schedule_id='{schedule_id}' was cancelled for steps: "
                f"{cancelled_step_names}. This should not happen, please report to developers."
            )
            _logger.error(message)
            await self._set_unexpected_opration_state(
                schedule_id, OperationErrorType.FRAMEWORK_ISSUE, message=message
            )
            return

        raise UnexpectedStepHandlingError(
            direction="revert", steps_statuses=steps_statuses, schedule_id=schedule_id
        )

    async def _set_unexpected_opration_state(
        self,
        schedule_id: ScheduleId,
        operation_error_type: OperationErrorType,
        message: str,
    ) -> None:
        schedule_data_proxy = ScheduleDataStoreProxy(
            store=self._store, schedule_id=schedule_id
        )
        await schedule_data_proxy.set_multiple(
            {
                "operation_error_type": operation_error_type,
                "operation_error_message": message,
            }
        )


async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    app.state.generic_scheduler_core = core = Core(app)
    await core.setup()
    yield {}
    await core.shutdown()


def get_core(app: FastAPI) -> Core:
    core: Core = app.state.generic_scheduler_core
    return core
