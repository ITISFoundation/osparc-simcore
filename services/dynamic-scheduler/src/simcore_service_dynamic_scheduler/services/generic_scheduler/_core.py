import asyncio
import logging
from collections.abc import Iterable
from contextlib import suppress
from datetime import timedelta
from typing import Final
from uuid import uuid4

from fastapi import FastAPI
from pydantic import NonNegativeInt
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.logging_utils import log_context
from servicelib.utils import limited_gather

from ._core_utils import (
    PARALLEL_REQUESTS,
    are_any_steps_in_a_progress_status,
    cleanup_after_finishing,
    get_group_step_proxies,
    get_requires_manual_intervention,
    get_step_error_traceback,
    get_steps_statuses,
    raise_if_overwrites_any_operation_provided_key,
    safe_event,
    set_unexpected_opration_state,
    start_and_mark_as_started,
    start_steps_which_were_not_started,
)
from ._deferred_runner import DeferredRunner
from ._errors import (
    CannotCancelWhileWaitingForManualInterventionError,
    NoDataFoundError,
    OperationNotCancellableError,
    StepNameNotInCurrentGroupError,
    StepNotInErrorStateError,
    StepNotWaitingForManualInterventionError,
    UnexpectedStepHandlingError,
)
from ._event import (
    enqueue_create_completed_event,
    enqueue_schedule_event,
    enqueue_undo_completed_event,
)
from ._event_after_registration import (
    register_to_start_after_on_created_completed,
    register_to_start_after_on_undo_completed,
)
from ._models import (
    EventType,
    OperationContext,
    OperationErrorType,
    OperationName,
    OperationToStart,
    ScheduleId,
    StepName,
    StepStatus,
)
from ._operation import (
    BaseStepGroup,
    Operation,
    OperationRegistry,
)
from ._store import (
    DeleteStepKeys,
    OperationContextProxy,
    OperationEventsProxy,
    ScheduleDataStoreProxy,
    StepGroupProxy,
    StepStoreProxy,
    Store,
)

_DEFAULT_UNKNOWN_STATUS_MAX_RETRY: Final[NonNegativeInt] = 3
_DEFAULT_UNKNOWN_STATUS_WAIT_BEFORE_RETRY: Final[timedelta] = timedelta(seconds=1)

_logger = logging.getLogger(__name__)


class Core(SingletonInAppStateMixin):
    app_state_name: str = "generic_scheduler_core"

    def __init__(
        self,
        app: FastAPI,
        unknown_status_max_retry: NonNegativeInt = _DEFAULT_UNKNOWN_STATUS_MAX_RETRY,
        unknown_status_wait_before_retry: timedelta = _DEFAULT_UNKNOWN_STATUS_WAIT_BEFORE_RETRY,
    ) -> None:
        self.app = app
        self.unknown_status_max_retry = unknown_status_max_retry
        self.unknown_status_wait_before_retry = unknown_status_wait_before_retry
        self._store: Store = Store.get_from_app_state(app)

    async def start_operation(
        self,
        operation_name: OperationName,
        initial_operation_context: OperationContext,
        on_create_completed: OperationToStart | None,
        on_undo_completed: OperationToStart | None,
    ) -> ScheduleId:
        """start an operation by it's given name and providing an initial context"""
        schedule_id: ScheduleId = f"{uuid4()}"

        # check if operation is registered
        operation = OperationRegistry.get_operation(operation_name)

        # NOTE: to ensure reproducibility of operations, the
        # operation steps cannot overwrite keys in the
        # initial context with their results
        raise_if_overwrites_any_operation_provided_key(
            operation, initial_operation_context
        )

        schedule_data_proxy = ScheduleDataStoreProxy(
            store=self._store, schedule_id=schedule_id
        )
        await schedule_data_proxy.create_or_update_multiple(
            {
                "operation_name": operation_name,
                "group_index": 0,
                "is_creating": True,
            }
        )

        operation_content_proxy = OperationContextProxy(
            store=self._store,
            schedule_id=schedule_id,
            operation_name=operation_name,
        )
        await operation_content_proxy.create_or_update(initial_operation_context)

        if on_create_completed:
            await register_to_start_after_on_created_completed(
                self.app, schedule_id, to_start=on_create_completed
            )

        if on_undo_completed:
            await register_to_start_after_on_undo_completed(
                self.app, schedule_id=schedule_id, to_start=on_undo_completed
            )

        await enqueue_schedule_event(self.app, schedule_id)
        return schedule_id

    async def cancel_operation(self, schedule_id: ScheduleId) -> None:
        """
        Sets the operation to undo form the point in which it arrived in:
        - when is_creating=True: cancels all steps & moves operation to undo
        - when is_creating=False: does nothing, since undo is already running

        # NOTE: SEE `_on_schedule_event` for more details
        """
        schedule_data_proxy = ScheduleDataStoreProxy(
            store=self._store, schedule_id=schedule_id
        )

        is_creating = await schedule_data_proxy.read("is_creating")

        if is_creating is False:
            _logger.warning(
                "Cannot cancel steps for schedule_id='%s' since UNDO is running",
                schedule_id,
            )
            return

        operation_name = await schedule_data_proxy.read("operation_name")
        group_index = await schedule_data_proxy.read("group_index")

        operation = OperationRegistry.get_operation(operation_name)

        if operation.is_cancellable is False:
            raise OperationNotCancellableError(operation_name=operation_name)

        group = operation[group_index]

        group_step_proxies = get_group_step_proxies(
            self._store,
            schedule_id=schedule_id,
            operation_name=operation_name,
            group_index=group_index,
            step_group=group,
            is_creating=is_creating,
        )

        # not allowed to cancel while waiting for manual intervention
        if any(
            await limited_gather(
                *(
                    get_requires_manual_intervention(step)
                    for step in group_step_proxies.values()
                ),
                limit=PARALLEL_REQUESTS,
            )
        ):
            raise CannotCancelWhileWaitingForManualInterventionError(
                schedule_id=schedule_id
            )

        async def _cancel_step(step_name: StepName, step_proxy: StepStoreProxy) -> None:
            with log_context(  # noqa: SIM117
                _logger,
                logging.DEBUG,
                f"Cancelling step {step_name=} of {operation_name=} for {schedule_id=}",
            ):
                with suppress(NoDataFoundError):
                    deferred_task_uid = await step_proxy.read("deferred_task_uid")
                    await DeferredRunner.cancel(deferred_task_uid)
                    await step_proxy.create_or_update("status", StepStatus.CANCELLED)

        await limited_gather(
            *(
                _cancel_step(step_name, step_proxy)
                for step_name, step_proxy in group_step_proxies.items()
            ),
            limit=PARALLEL_REQUESTS,
        )

    async def restart_operation_step_stuck_in_error(
        self,
        schedule_id: ScheduleId,
        step_name: StepName,
        *,
        in_manual_intervention: bool,
    ) -> None:
        """
        Force a step stuck in an error state to retry.
        Will raise errors if step cannot be retried.
        """
        schedule_data_proxy = ScheduleDataStoreProxy(
            store=self._store, schedule_id=schedule_id
        )
        is_creating = await schedule_data_proxy.read("is_creating")
        operation_name = await schedule_data_proxy.read("operation_name")
        group_index = await schedule_data_proxy.read("group_index")

        operation = OperationRegistry.get_operation(operation_name)
        step_group = operation[group_index]
        step_group_name = step_group.get_step_group_name(index=group_index)

        if step_name not in {
            step.get_step_name() for step in step_group.get_step_subgroup_to_run()
        }:
            raise StepNameNotInCurrentGroupError(
                step_name=step_name,
                step_group_name=step_group_name,
                operation_name=operation_name,
            )

        step_proxy = StepStoreProxy(
            store=self._store,
            schedule_id=schedule_id,
            operation_name=operation_name,
            step_group_name=step_group_name,
            step_name=step_name,
            is_creating=is_creating,
        )

        try:
            await step_proxy.read("error_traceback")
        except NoDataFoundError as exc:
            raise StepNotInErrorStateError(step_name=step_name) from exc

        step_keys_to_remove: list[DeleteStepKeys] = [
            "deferred_created",
            "error_traceback",
            "deferred_task_uid",
        ]
        if in_manual_intervention:
            requires_manual_intervention: bool = False
            with suppress(NoDataFoundError):
                requires_manual_intervention = await step_proxy.read(
                    "requires_manual_intervention"
                )

            if requires_manual_intervention is False:
                raise StepNotWaitingForManualInterventionError(step_name=step_name)

            step_keys_to_remove.append("requires_manual_intervention")

        # restart the step
        schedule_data_proxy = ScheduleDataStoreProxy(
            store=self._store, schedule_id=schedule_id
        )
        group_proxy = StepGroupProxy(
            store=self._store,
            schedule_id=schedule_id,
            operation_name=operation_name,
            step_group_name=step_group_name,
            is_creating=is_creating,
        )

        # remove previus entries for the step
        await step_proxy.delete_keys(*step_keys_to_remove)
        await schedule_data_proxy.delete_keys(
            "operation_error_type", "operation_error_message"
        )
        await group_proxy.decrement_and_get_done_steps_count()

        _logger.debug(
            "Restarting step_name='%s' of operation_name='%s' for schedule_id='%s' after '%s'",
            step_name,
            operation_name,
            schedule_id,
            "manual intervention" if in_manual_intervention else "error in undo",
        )
        # restart only this step
        await start_and_mark_as_started(
            step_proxy,
            is_creating=is_creating,
            expected_steps_count=len(step_group),
        )

    async def safe_on_schedule_event(self, schedule_id: ScheduleId) -> None:
        async with safe_event(self._store, schedule_id):
            with log_context(
                _logger,
                logging.DEBUG,
                f"processing schedule_event for schedule_id={schedule_id}",
                log_duration=True,
            ):
                await self._on_schedule_event(schedule_id)

    async def _on_schedule_event(self, schedule_id: ScheduleId) -> None:
        """
        A schedule event is what advances the `operation` processing. Multiple schedule events
        are required to complete an operation.

        An `operation` is moved from one `step group` to the next one until all `steps` are done.
        Steps: always finish, automatically retry and are guaranteed to be in a final state
        (SUCCESS, FAILED, CANCELLED).
        Processing continues when all steps are in a final state.

        From this point onwards an `operation` can be advanced in one the following modes:
        - `CEREATEING`: default mode when starting an operation
            - runs the `create()` of each step in each group (`first` -> `last` group)
            - when done, it removes all operation data
        - `UNDOING`: undo the actions of `create()` in reverse order with respect to CREATING
            - runs the `undo()` of each step in each group (`current` -> `first` group)
            - when done, it removes all operation data
        - `REPEATING`: repeats the `create()` of all steps in a group
            - waits and runs the `create()` of all the steps in last group in the operation
            - never completes, unless operation is cancelled

        NOTE: `REPEATING` is triggered by setting `BaseStepGroup(repeat_steps=True)` during definition
        of an `operation`.
        NOTE: `UNDOING` is triggered by calling `cancel_operation()` or when a step finishes with
        status `FAILED` or `CANCELLED` (except in manual intervention).

        There are 3 reasons why an operation will hang:
        - MANUAL_INTERVENTION: step failed during `create()` and flagged for manual intervention
            -> requires support intervention
        - STEP_ISSUE: a step failed during `undo()` due to an error in the step's undo code
            -> unexpected behviour / requires developer intervention
        - FRAMEWORK_ISSUE: a step failed during `undo()` because it was cancelled
            -> unexpected behviour / requires developer intervention

        NOTE: only MANUAL_INTERVENTION is an allowed to happen all other failuires are to be treated
        as bugs and reported.
        """
        schedule_data_proxy = ScheduleDataStoreProxy(
            store=self._store, schedule_id=schedule_id
        )

        operation_name = await schedule_data_proxy.read("operation_name")
        is_creating = await schedule_data_proxy.read("is_creating")
        group_index = await schedule_data_proxy.read("group_index")

        operation = OperationRegistry.get_operation(operation_name)
        step_group = operation[group_index]

        group_step_proxies = get_group_step_proxies(
            self._store,
            schedule_id=schedule_id,
            operation_name=operation_name,
            group_index=group_index,
            step_group=step_group,
            is_creating=is_creating,
        )

        # 1) ensure all operation steps in the group are started before advancing
        if await start_steps_which_were_not_started(
            group_step_proxies,
            is_creating=is_creating,
            group_step_count=len(step_group),
        ):
            return

        # 2) wait for all steps to finish before advancing
        steps_statuses = await get_steps_statuses(group_step_proxies.values())
        _logger.debug(
            "DETECTED: steps_statuses=%s in operation=%s for scheuled_id=%s",
            steps_statuses,
            operation_name,
            schedule_id,
        )
        if are_any_steps_in_a_progress_status(steps_statuses):
            _logger.debug(
                "operation_name='%s' has steps still in progress steps_statuses='%s'",
                operation_name,
                group_step_proxies,
            )
            return

        # 3) advancing operation in mode
        step_group_name = step_group.get_step_group_name(index=group_index)
        base_message = f"{step_group_name=} in {operation_name=} for {schedule_id=}"

        if step_group.repeat_steps is True and is_creating:
            with log_context(_logger, logging.DEBUG, f"REPEATING {base_message}"):
                await self._advance_as_repeating(
                    schedule_data_proxy,
                    schedule_id,
                    operation_name,
                    group_index,
                    step_group,
                    group_step_proxies,
                )

        elif is_creating:
            with log_context(_logger, logging.DEBUG, f"CREATING {base_message}"):
                await self._advance_as_creating(
                    steps_statuses,
                    schedule_data_proxy,
                    schedule_id,
                    operation_name,
                    group_index,
                    step_group,
                    operation,
                )

        else:
            with log_context(_logger, logging.DEBUG, f"UNDOING {base_message}"):
                await self._advance_as_undoing(
                    steps_statuses,
                    schedule_data_proxy,
                    schedule_id,
                    operation_name,
                    group_index,
                    step_group,
                )

    async def _advance_as_repeating(
        self,
        schedule_data_proxy: ScheduleDataStoreProxy,
        schedule_id: ScheduleId,
        operation_name: OperationName,
        group_index: NonNegativeInt,
        current_step_group: BaseStepGroup,
        group_step_proxies: dict[StepName, StepStoreProxy],
    ) -> None:
        # REPEATING logic:
        # 1) sleep before repeating
        # 2) if any of the repeating steps was cancelled -> move to undo
        # 3) -> restart all steps in the group

        step_proxies: Iterable[StepStoreProxy] = group_step_proxies.values()

        # 1) sleep before repeating
        await asyncio.sleep(current_step_group.wait_before_repeat.total_seconds())

        # 2) if any of the repeating steps was cancelled -> move to undo

        # since some time passed, query all steps statuses again,
        # a cancellation request might have been requested
        steps_stauses = await get_steps_statuses(step_proxies)
        if any(status == StepStatus.CANCELLED for status in steps_stauses.values()):
            # NOTE:
            await schedule_data_proxy.create_or_update("is_creating", value=False)
            await enqueue_schedule_event(self.app, schedule_id)
            return

        # 3) -> restart all steps in the group
        await limited_gather(
            *(x.delete() for x in step_proxies), limit=PARALLEL_REQUESTS
        )
        group_proxy = StepGroupProxy(
            store=self._store,
            schedule_id=schedule_id,
            operation_name=operation_name,
            step_group_name=current_step_group.get_step_group_name(index=group_index),
            is_creating=True,
        )
        await group_proxy.delete()
        await enqueue_schedule_event(self.app, schedule_id)

    async def _advance_as_creating(
        self,
        steps_statuses: dict[StepName, StepStatus],
        schedule_data_proxy: ScheduleDataStoreProxy,
        schedule_id: ScheduleId,
        operation_name: OperationName,
        group_index: NonNegativeInt,
        current_step_group: BaseStepGroup,
        operation: Operation,
    ) -> None:
        # CREATION logic:
        # 1) if all steps in group in SUUCESS
        # - 1a) -> move to next group
        # - 1b) if reached the end of the CREATE operation -> remove all created data [EMIT create complete event]
        # 2) if manual intervention is required -> do nothing else
        # 3) if any step in CANCELLED or FAILED (and not in manual intervention) -> move to undo

        # 1) if all steps in group in SUUCESS
        if all(status == StepStatus.SUCCESS for status in steps_statuses.values()):

            # 1a) -> move to next group
            try:
                next_group_index = group_index + 1
                # does a next group exist?
                _ = operation[next_group_index]
                await schedule_data_proxy.create_or_update(
                    "group_index", value=next_group_index
                )
                await enqueue_schedule_event(self.app, schedule_id)
            except IndexError:

                # 1b) if reached the end of the CREATE operation -> remove all created data [EMIT create complete event]
                on_created_proxy = OperationEventsProxy(
                    self._store, schedule_id, EventType.ON_CREATED_COMPLETED
                )
                operation_name: OperationName | None = None
                initial_context: OperationContext | None = None
                if await on_created_proxy.exists():
                    operation_name = await on_created_proxy.read("operation_name")
                    initial_context = await on_created_proxy.read("initial_context")

                await cleanup_after_finishing(
                    self._store, schedule_id=schedule_id, is_creating=True
                )
                if operation_name is not None and initial_context is not None:
                    await enqueue_create_completed_event(
                        self.app, schedule_id, operation_name, initial_context
                    )

            return

        # 2) if manual intervention is required -> do nothing else
        manual_intervention_step_names: set[StepName] = set()
        current_step_group.get_step_subgroup_to_run()
        for step in current_step_group.get_step_subgroup_to_run():
            step_status = steps_statuses.get(step.get_step_name(), None)
            if step_status == StepStatus.FAILED and step.wait_for_manual_intervention():
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
                await step_proxy.create_or_update(
                    "requires_manual_intervention", value=True
                )
                manual_intervention_step_names.add(step.get_step_name())

        if manual_intervention_step_names:
            message = (
                f"Operation '{operation_name}' for schedule_id='{schedule_id}' "
                f"requires manual intervention for steps: {manual_intervention_step_names}"
            )
            _logger.warning(message)
            await set_unexpected_opration_state(
                self._store, schedule_id, OperationErrorType.STEP_ISSUE, message=message
            )
            return

        # 3) if any step in CANCELLED or FAILED (and not in manual intervention) -> move to undo
        if any(
            s in {StepStatus.FAILED, StepStatus.CANCELLED}
            for s in steps_statuses.values()
        ):
            with log_context(
                _logger,
                logging.DEBUG,
                f"{operation_name=} was not successfull: {steps_statuses=}, moving to undo",
            ):
                await schedule_data_proxy.create_or_update("is_creating", value=False)
                await enqueue_schedule_event(self.app, schedule_id)
            return

        raise UnexpectedStepHandlingError(
            direction="creation", steps_statuses=steps_statuses, schedule_id=schedule_id
        )

    async def _advance_as_undoing(
        self,
        steps_statuses: dict[StepName, StepStatus],
        schedule_data_proxy: ScheduleDataStoreProxy,
        schedule_id: ScheduleId,
        operation_name: OperationName,
        group_index: NonNegativeInt,
        current_step_group: BaseStepGroup,
    ) -> None:
        # UNDO logic:
        # 1) if all steps in group in SUCCESS
        # - 1a) if reached the end of the UNDO operation -> remove all created data [EMIT undo complete event]
        # - 1b) -> move to previous group
        # 2) it is unexpected to have a FAILED step -> do nothing else
        # 3) it is unexpected to have a CANCELLED step -> do nothing else

        # 1) if all steps in group in SUCCESS
        if all(s == StepStatus.SUCCESS for s in steps_statuses.values()):
            previous_group_index = group_index - 1
            if previous_group_index < 0:

                # 1a) if reached the end of the UNDO operation -> remove all created data [EMIT undo complete event]
                on_undo_proxy = OperationEventsProxy(
                    self._store, schedule_id, EventType.ON_UNDO_COMPLETED
                )
                operation_name: OperationName | None = None
                initial_context: OperationContext | None = None
                if await on_undo_proxy.exists():
                    operation_name = await on_undo_proxy.read("operation_name")
                    initial_context = await on_undo_proxy.read("initial_context")

                await cleanup_after_finishing(
                    self._store, schedule_id=schedule_id, is_creating=False
                )
                if operation_name is not None and initial_context is not None:
                    await enqueue_undo_completed_event(
                        self.app, schedule_id, operation_name, initial_context
                    )
                return

            # 1b) -> move to previous group
            await schedule_data_proxy.create_or_update(
                "group_index", value=previous_group_index
            )
            await enqueue_schedule_event(self.app, schedule_id)
            return

        # 2) it is unexpected to have a FAILED step -> do nothing else
        if failed_step_names := [
            n for n, s in steps_statuses.items() if s == StepStatus.FAILED
        ]:
            error_tracebacks: list[tuple[StepName, str]] = await limited_gather(
                *(
                    get_step_error_traceback(
                        self._store,
                        schedule_id=schedule_id,
                        operation_name=operation_name,
                        current_step_group=current_step_group,
                        group_index=group_index,
                        step_name=step_name,
                    )
                    for step_name in failed_step_names
                ),
                limit=PARALLEL_REQUESTS,
            )

            formatted_tracebacks = "\n".join(
                f"Step '{step_name}':\n{traceback}"
                for step_name, traceback in error_tracebacks
            )
            message = (
                f"Operation 'undo' for schedule_id='{schedule_id}' failed for steps: "
                f"'{failed_step_names}'. Step code should never fail during destruction, "
                f"please report to developers:\n{formatted_tracebacks}"
            )
            _logger.error(message)
            await set_unexpected_opration_state(
                self._store, schedule_id, OperationErrorType.STEP_ISSUE, message=message
            )
            return

        # 3) it is unexpected to have a CANCELLED step -> do nothing else
        if cancelled_step_names := [
            n for n, s in steps_statuses.items() if s == StepStatus.CANCELLED
        ]:
            message = (
                f"Operation 'undo' for schedule_id='{schedule_id}' was cancelled for steps: "
                f"{cancelled_step_names}. This should not happen, and should be addressed."
            )
            _logger.error(message)
            await set_unexpected_opration_state(
                self._store,
                schedule_id,
                OperationErrorType.FRAMEWORK_ISSUE,
                message=message,
            )
            return

        raise UnexpectedStepHandlingError(
            direction="undo", steps_statuses=steps_statuses, schedule_id=schedule_id
        )


async def start_operation(
    app: FastAPI,
    operation_name: OperationName,
    initial_operation_context: OperationContext,
    *,
    on_create_completed: OperationToStart | None = None,
    on_undo_completed: OperationToStart | None = None,
) -> ScheduleId:
    return await Core.get_from_app_state(app).start_operation(
        operation_name,
        initial_operation_context,
        on_create_completed,
        on_undo_completed,
    )


async def cancel_operation(app: FastAPI, schedule_id: ScheduleId) -> None:
    """
    Unstruct scheduler to undo all steps completed until
    now for the running operation.

    `undoing` refers to the act of undoing the effects of a step
    that has already been completed (eg: remove a created network)
    """
    await Core.get_from_app_state(app).cancel_operation(schedule_id)


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
    await Core.get_from_app_state(app).restart_operation_step_stuck_in_error(
        schedule_id, step_name, in_manual_intervention=True
    )


async def restart_operation_step_stuck_during_undo(
    app: FastAPI, schedule_id: ScheduleId, step_name: StepName
) -> None:
    """
    Restarts a `stuck step` while the operation is being undone

    `stuck step` is a step that has failed and exhausted all retries
    `undoing` refers to the act of undoing the effects of a step
    that has already been completed (eg: remove a created network)
    """
    await Core.get_from_app_state(app).restart_operation_step_stuck_in_error(
        schedule_id, step_name, in_manual_intervention=False
    )
