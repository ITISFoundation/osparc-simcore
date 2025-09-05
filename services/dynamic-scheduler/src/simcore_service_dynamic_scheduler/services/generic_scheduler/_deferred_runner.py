from datetime import timedelta

from fastapi import FastAPI
from servicelib.deferred_tasks import BaseDeferredHandler, DeferredContext, TaskUID
from servicelib.deferred_tasks._models import TaskResultError

from ._models import OperationName, ScheduleId, StepGroupName, StepName, StepStatus
from ._operation import BaseStep, OperationRegistry
from ._store import StepStoreProxy, Store, get_store


def _get_step_store_proxy(context: DeferredContext) -> StepStoreProxy:
    app: FastAPI = context["app"]
    schedule_id: ScheduleId = context["schedule_id"]
    operation_name: OperationName = context["operation_name"]
    step_group_name: StepGroupName = context["step_group_name"]
    step_name: StepName = context["step_name"]
    is_creating = context["is_creating"]

    store: Store = get_store(app)
    return StepStoreProxy(
        store=store,
        schedule_id=schedule_id,
        operation_name=operation_name,
        step_group_name=step_group_name,
        step_name=step_name,
        is_creating=is_creating,
    )


def _get_step(context: DeferredContext) -> type[BaseStep]:
    operation_name: OperationName = context["operation_name"]
    step_name: StepName = context["step_name"]
    return OperationRegistry.get_step(operation_name, step_name)


class DeferredRunner(BaseDeferredHandler[None]):
    @classmethod
    async def start(  # type:ignore[override] # pylint:disable=arguments-differ
        cls,
        *,
        schedule_id: ScheduleId,
        operation_name: OperationName,
        step_group_name: StepGroupName,
        step_name: StepName,
        is_creating: bool,
    ) -> DeferredContext:
        return {
            "schedule_id": schedule_id,
            "operation_name": operation_name,
            "step_group_name": step_group_name,
            "step_name": step_name,
            "is_creating": is_creating,
        }

    @classmethod
    async def get_retries(cls, context: DeferredContext) -> int:
        is_creating = context["is_creating"]
        step = _get_step(context)
        return (
            await step.get_create_retries(context)
            if is_creating
            else await step.get_destroy_retries(context)
        )

    @classmethod
    async def get_timeout(cls, context: DeferredContext) -> timedelta:
        is_creating = context["is_creating"]
        step = _get_step(context)
        return (
            await step.get_create_timeout(context)
            if is_creating
            else await step.get_destroy_timeout(context)
        )

    @classmethod
    async def on_created(cls, task_uid: TaskUID, context: DeferredContext) -> None:
        await _get_step_store_proxy(context).set_multiple(
            {"deferred_task_uid": task_uid, "status": StepStatus.CREATED}
        )

    @classmethod
    async def run(cls, context: DeferredContext) -> None:
        app = context["app"]
        is_creating = context["is_creating"]

        await _get_step_store_proxy(context).set("status", StepStatus.RUNNING)

        step = _get_step(context)

        if is_creating:
            await step.create(app)
        else:
            await step.destroy(app)

    @classmethod
    async def on_result(cls, result: None, context: DeferredContext) -> None:
        _ = result
        await _get_step_store_proxy(context).set("status", StepStatus.SUCCESS)

    @classmethod
    async def on_finished_with_error(
        cls, error: TaskResultError, context: DeferredContext
    ) -> None:
        await _get_step_store_proxy(context).set_multiple(
            {"status": StepStatus.FAILED, "error_traceback": error.format_error()}
        )

    @classmethod
    async def on_cancelled(cls, context: DeferredContext) -> None:
        await _get_step_store_proxy(context).set("status", StepStatus.CANCELLED)
