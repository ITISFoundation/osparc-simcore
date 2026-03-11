from datetime import timedelta

from fastapi import FastAPI
from pydantic import NonNegativeInt
from servicelib.deferred_tasks import BaseDeferredHandler, DeferredContext, TaskUID
from servicelib.deferred_tasks._models import TaskResultError

from ._errors import (
    OperationContextValueIsNoneError,
    ProvidedOperationContextKeysAreMissingError,
)
from ._event import enqueue_schedule_event
from ._models import (
    OperationContext,
    OperationName,
    ProvidedOperationContext,
    ScheduleId,
    StepGroupName,
    StepName,
    StepStatus,
)
from ._operation import BaseStep, OperationRegistry
from ._store import (
    OperationContextProxy,
    StepGroupProxy,
    StepStoreProxy,
    Store,
)


def get_step_store_proxy(context: DeferredContext) -> StepStoreProxy:
    app: FastAPI = context["app"]
    schedule_id: ScheduleId = context["schedule_id"]
    operation_name: OperationName = context["operation_name"]
    step_group_name: StepGroupName = context["step_group_name"]
    step_name: StepName = context["step_name"]
    is_executing = context["is_executing"]

    return StepStoreProxy(
        store=Store.get_from_app_state(app),
        schedule_id=schedule_id,
        operation_name=operation_name,
        step_group_name=step_group_name,
        step_name=step_name,
        is_executing=is_executing,
    )


def get_step_group_proxy(context: DeferredContext) -> StepGroupProxy:
    app: FastAPI = context["app"]
    schedule_id: ScheduleId = context["schedule_id"]
    operation_name: OperationName = context["operation_name"]
    step_group_name: StepGroupName = context["step_group_name"]
    is_executing = context["is_executing"]

    return StepGroupProxy(
        store=Store.get_from_app_state(app),
        schedule_id=schedule_id,
        operation_name=operation_name,
        step_group_name=step_group_name,
        is_executing=is_executing,
    )


def get_operation_context_proxy(context: DeferredContext) -> OperationContextProxy:
    app: FastAPI = context["app"]
    schedule_id: ScheduleId = context["schedule_id"]
    operation_name: OperationName = context["operation_name"]

    return OperationContextProxy(
        store=Store.get_from_app_state(app),
        schedule_id=schedule_id,
        operation_name=operation_name,
    )


def _get_step(context: DeferredContext) -> type[BaseStep]:
    operation_name: OperationName = context["operation_name"]
    step_name: StepName = context["step_name"]
    return OperationRegistry.get_step(operation_name, step_name)


async def _enqueue_schedule_event_if_group_is_done(context: DeferredContext) -> None:
    # used to avoid concurrency issues when multiples steps finish "at the same time"
    app: FastAPI = context["app"]
    schedule_id: ScheduleId = context["schedule_id"]
    expected_steps_count: NonNegativeInt = context["expected_steps_count"]

    if await get_step_group_proxy(context).increment_and_get_done_steps_count() == expected_steps_count:
        await enqueue_schedule_event(app, schedule_id)


def _raise_if_any_context_value_is_none(
    operation_context: OperationContext,
) -> None:
    if any(value is None for value in operation_context.values()):
        raise OperationContextValueIsNoneError(operation_context=operation_context)


def _raise_if_provided_context_keys_are_missing_or_none(
    provided_context: ProvidedOperationContext,
    expected_keys: set[str],
) -> None:
    missing_keys = expected_keys - provided_context.keys()
    if missing_keys:
        raise ProvidedOperationContextKeysAreMissingError(
            provided_context=provided_context,
            missing_keys=missing_keys,
            expected_keys=expected_keys,
        )

    _raise_if_any_context_value_is_none(provided_context)


class DeferredRunner(BaseDeferredHandler[None]):
    @classmethod
    async def start(  # type:ignore[override] # pylint:disable=arguments-differ
        cls,
        *,
        schedule_id: ScheduleId,
        operation_name: OperationName,
        step_group_name: StepGroupName,
        step_name: StepName,
        is_executing: bool,
        expected_steps_count: NonNegativeInt,
    ) -> DeferredContext:
        return {
            "schedule_id": schedule_id,
            "operation_name": operation_name,
            "step_group_name": step_group_name,
            "step_name": step_name,
            "is_executing": is_executing,
            "expected_steps_count": expected_steps_count,
        }

    @classmethod
    async def get_retries(cls, context: DeferredContext) -> int:
        is_executing = context["is_executing"]
        step = _get_step(context)
        return await step.get_execute_retries(context) if is_executing else await step.get_revert_retries(context)

    @classmethod
    async def get_timeout(cls, context: DeferredContext) -> timedelta:
        is_executing = context["is_executing"]
        step = _get_step(context)
        return (
            await step.get_execute_wait_between_attempts(context)
            if is_executing
            else await step.get_revert_wait_between_attempts(context)
        )

    @classmethod
    async def on_created(cls, task_uid: TaskUID, context: DeferredContext) -> None:
        await get_step_store_proxy(context).create_or_update_multiple(
            {"deferred_task_uid": task_uid, "status": StepStatus.CREATED}
        )

    @classmethod
    async def run(cls, context: DeferredContext) -> None:
        app = context["app"]
        is_executing = context["is_executing"]

        await get_step_store_proxy(context).create_or_update("status", StepStatus.RUNNING)

        step = _get_step(context)

        operation_context_proxy = get_operation_context_proxy(context)

        if is_executing:
            required_context = await operation_context_proxy.read(*step.get_execute_requires_context_keys())
            _raise_if_any_context_value_is_none(required_context)

            step_provided_operation_context = await step.execute(app, required_context)
            provided_operation_context = step_provided_operation_context or {}
            execute_provides_keys = step.get_execute_provides_context_keys()

            _raise_if_provided_context_keys_are_missing_or_none(provided_operation_context, execute_provides_keys)
        else:
            required_context = await operation_context_proxy.read(*step.get_revert_requires_context_keys())
            _raise_if_any_context_value_is_none(required_context)

            step_provided_operation_context = await step.revert(app, required_context)
            provided_operation_context = step_provided_operation_context or {}
            revert_provides_keys = step.get_revert_provides_context_keys()

            _raise_if_provided_context_keys_are_missing_or_none(provided_operation_context, revert_provides_keys)

        await operation_context_proxy.create_or_update(provided_operation_context)

    @classmethod
    async def on_result(cls, result: None, context: DeferredContext) -> None:
        _ = result
        await get_step_store_proxy(context).create_or_update("status", StepStatus.SUCCESS)

        await _enqueue_schedule_event_if_group_is_done(context)

    @classmethod
    async def on_finished_with_error(cls, error: TaskResultError, context: DeferredContext) -> None:
        await get_step_store_proxy(context).create_or_update_multiple(
            {"status": StepStatus.FAILED, "error_traceback": error.format_error()}
        )

        await _enqueue_schedule_event_if_group_is_done(context)
