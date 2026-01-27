import logging
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from typing import Final

from common_library.error_codes import create_error_code
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from pydantic import NonNegativeInt
from servicelib.logging_utils import log_context
from servicelib.utils import limited_gather

from ._deferred_runner import DeferredRunner
from ._errors import (
    InitialOperationContextKeyNotAllowedError,
    NoDataFoundError,
)
from ._models import (
    OperationContext,
    OperationErrorType,
    OperationName,
    ScheduleId,
    StepName,
    StepStatus,
)
from ._operation import (
    BaseStepGroup,
    Operation,
    get_operation_provided_context_keys,
)
from ._store import (
    OperationRemovalProxy,
    ScheduleDataStoreProxy,
    StepStoreProxy,
    Store,
)

_logger = logging.getLogger(__name__)


PARALLEL_REQUESTS: Final[NonNegativeInt] = 5


_IN_PROGRESS_STATUSES: Final[set[StepStatus]] = {
    StepStatus.SCHEDULED,
    StepStatus.CREATED,
    StepStatus.RUNNING,
}


def are_any_steps_in_a_progress_status(
    steps_statuses: dict[StepName, StepStatus],
) -> bool:
    return any(status in _IN_PROGRESS_STATUSES for status in steps_statuses.values())


async def _get_step_status(step_proxy: StepStoreProxy) -> tuple[StepName, StepStatus]:
    try:
        status = await step_proxy.read("status")
    except NoDataFoundError:
        status = StepStatus.UNKNOWN

    return step_proxy.step_name, status


async def get_steps_statuses(
    step_proxies: Iterable[StepStoreProxy],
) -> dict[StepName, StepStatus]:
    result: list[tuple[StepName, StepStatus]] = await limited_gather(
        *(_get_step_status(step) for step in step_proxies),
        limit=PARALLEL_REQUESTS,
    )
    return dict(result)


async def start_and_mark_as_started(
    step_proxy: StepStoreProxy,
    *,
    is_executing: bool,
    expected_steps_count: NonNegativeInt,
) -> None:
    await DeferredRunner.start(
        schedule_id=step_proxy.schedule_id,
        operation_name=step_proxy.operation_name,
        step_group_name=step_proxy.step_group_name,
        step_name=step_proxy.step_name,
        is_executing=is_executing,
        expected_steps_count=expected_steps_count,
    )
    await step_proxy.create_or_update_multiple({"deferred_created": True, "status": StepStatus.SCHEDULED})


def raise_if_overwrites_any_operation_provided_key(
    operation: Operation, initial_operation_context: OperationContext
) -> None:
    operation_provided_context_keys = get_operation_provided_context_keys(operation)
    for key in initial_operation_context:
        if key in operation_provided_context_keys:
            raise InitialOperationContextKeyNotAllowedError(key=key, operation=operation)


async def get_step_error_traceback(
    store: Store,
    *,
    schedule_id: ScheduleId,
    operation_name: OperationName,
    current_step_group: BaseStepGroup,
    group_index: NonNegativeInt,
    step_name: StepName,
) -> tuple[StepName, str]:
    step_proxy = StepStoreProxy(
        store=store,
        schedule_id=schedule_id,
        operation_name=operation_name,
        step_group_name=current_step_group.get_step_group_name(index=group_index),
        step_name=step_name,
        is_executing=False,
    )
    return step_name, await step_proxy.read("error_traceback")


def get_group_step_proxies(
    store: Store,
    *,
    schedule_id: ScheduleId,
    operation_name: OperationName,
    group_index: NonNegativeInt,
    step_group: BaseStepGroup,
    is_executing: bool,
) -> dict[StepName, StepStoreProxy]:
    return {
        step.get_step_name(): StepStoreProxy(
            store=store,
            schedule_id=schedule_id,
            operation_name=operation_name,
            step_group_name=step_group.get_step_group_name(index=group_index),
            step_name=step.get_step_name(),
            is_executing=is_executing,
        )
        for step in step_group.get_step_subgroup_to_run()
    }


async def _get_was_step_started(
    step_proxy: StepStoreProxy,
) -> tuple[bool, StepStoreProxy]:
    try:
        was_stated = (await step_proxy.read("deferred_created")) is True
    except NoDataFoundError:
        was_stated = False

    return was_stated, step_proxy


async def _get_steps_to_start(
    step_proxies: Iterable[StepStoreProxy],
) -> list[StepStoreProxy]:
    result: list[tuple[bool, StepStoreProxy]] = await limited_gather(
        *(_get_was_step_started(step) for step in step_proxies),
        limit=PARALLEL_REQUESTS,
    )
    return [proxy for was_started, proxy in result if was_started is False]


async def start_steps_which_were_not_started(
    group_step_proxies: dict[StepName, StepStoreProxy],
    *,
    is_executing: bool,
    group_step_count: NonNegativeInt,
) -> bool:
    """returns True if any step was started"""
    started_count: NonNegativeInt = 0
    if to_start_step_proxies := await _get_steps_to_start(group_step_proxies.values()):
        steps_to_start_names = [step_proxy.step_name for step_proxy in to_start_step_proxies]
        with log_context(
            _logger,
            logging.DEBUG,
            f"starting steps: {steps_to_start_names=}",
        ):
            await limited_gather(
                *(
                    start_and_mark_as_started(
                        step_proxy,
                        is_executing=is_executing,
                        expected_steps_count=group_step_count,
                    )
                    for step_proxy in to_start_step_proxies
                ),
                limit=PARALLEL_REQUESTS,
            )
        started_count = len(to_start_step_proxies)
    return started_count > 0


async def cleanup_after_finishing(store: Store, *, schedule_id: ScheduleId, is_executing: bool) -> None:
    removal_proxy = OperationRemovalProxy(store=store, schedule_id=schedule_id)
    await removal_proxy.delete()
    verb = "COMPLETED" if is_executing else "REVERTED"
    _logger.debug("Operation for schedule_id='%s' %s successfully", verb, schedule_id)


async def get_requires_manual_intervention(step_proxy: StepStoreProxy) -> bool:
    try:
        return await step_proxy.read("requires_manual_intervention")
    except NoDataFoundError:
        return False


async def set_unexpected_operation_state(
    store: Store,
    schedule_id: ScheduleId,
    operation_error_type: OperationErrorType,
    message: str,
) -> None:
    schedule_data_proxy = ScheduleDataStoreProxy(store=store, schedule_id=schedule_id)
    await schedule_data_proxy.create_or_update_multiple(
        {
            "operation_error_type": operation_error_type,
            "operation_error_message": message,
        }
    )


@asynccontextmanager
async def safe_event(store: Store, schedule_id: ScheduleId) -> AsyncIterator[None]:
    try:
        yield
    except NoDataFoundError as err:
        _logger.debug(
            "Cannot process schedule_id='%s' since it's data was not found: %s",
            schedule_id,
            err,
        )
    except Exception as err:  # pylint:disable=broad-exception-caught
        error_code = create_error_code(err)
        log_kwargs = create_troubleshooting_log_kwargs(
            "Unexpected error during scheduling",
            error=err,
            error_code=error_code,
            error_context={"schedule_id": schedule_id},
            tip="This is a bug, please report it to the developers",
        )
        _logger.exception(**log_kwargs)
        await set_unexpected_operation_state(
            store,
            schedule_id,
            OperationErrorType.FRAMEWORK_ISSUE,
            message=log_kwargs["msg"],
        )
