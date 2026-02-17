import asyncio
import logging
from asyncio import Queue, QueueFull, Task, create_task
from contextlib import suppress
from datetime import timedelta
from enum import auto
from functools import cached_property, partial
from typing import Any, Final
from uuid import uuid4

from common_library.async_tools import cancel_wait_task
from common_library.logging.logging_errors import create_troubleshooting_log_message
from fastapi import FastAPI
from models_library.utils.enums import StrAutoEnum
from pydantic import NonNegativeInt
from servicelib.background_task import create_periodic_task, periodic
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.logging_utils import log_context

from ..base_repository import get_repository
from ._lifecycle_protocol import SupportsLifecycle
from ._metrics import MetricsManager
from ._models import InData, InDataKeys, OutData, OutDataKeys, Step, StepId, WorkerId
from ._notifications import RK_STEP_CANCELLED, RK_STEP_READY, NotificationsManager
from ._queue import BoundedPubSubQueue, get_consumer_count
from ._repositories import RunsStoreRepository, StepsLeaseRepository, StepsRepository
from ._worker_utils import ChangeNotifier
from ._workflow_registry import WorkflowRegistry

_logger = logging.getLogger(__name__)


class _InterruptReasson(StrAutoEnum):
    USER_CANCELLATION_REQUESTED = auto()
    LEASE_EXPIRY = auto()
    STEP_COMPLETED = auto()


async def _push_output_context(
    step: Step, runs_store_repo: RunsStoreRepository, output_context: OutData, provided_outputs: OutDataKeys
) -> None:
    output_context = output_context or {}

    push_to_store: dict[str, Any] = {}
    for key_config in provided_outputs:
        if key_config.optional:
            value = output_context.get(key_config.name)
            if value is not None:
                push_to_store[key_config.name] = value
        else:
            if key_config.name not in output_context:
                msg = f"required output key '{key_config.name}' not preset in {output_context=} for '{step.step_id=}'"
                raise KeyError(msg)
            push_to_store[key_config.name] = output_context[key_config.name]

    await runs_store_repo.set_to_store(step.run_id, push_to_store)


async def _get_input_context(
    app: FastAPI, step: Step, runs_store_repo: RunsStoreRepository, requested_inputs: InDataKeys
) -> InData:
    data_keys = {key_config.name for key_config in requested_inputs}
    stored_kvs = await runs_store_repo.get_from_store(step.run_id, data_keys)

    full_context: InData = {"app": app, **stored_kvs}

    context: InData = {}

    for key_config in requested_inputs:
        if key_config.optional:
            context[key_config.name] = full_context.get(key_config.name)
        else:
            if key_config.name not in full_context:
                msg = f"required input key '{key_config.name}' not preset in {context=} for '{step.step_id=}'"
                raise KeyError(msg)
            context[key_config.name] = full_context[key_config.name]

    return context


async def _task_step_runner(app: FastAPI, step: Step, interrupt_queue: Queue[_InterruptReasson]) -> None:
    try:
        workflow_registry = WorkflowRegistry.get_from_app_state(app)
        step_class = workflow_registry.get_base_step(step.step_type)
        runs_store_repo = get_repository(app, RunsStoreRepository)

        if step.is_reverting:
            revert_in_context = await _get_input_context(
                app, step, runs_store_repo, step_class.revert_requests_inputs()
            )
            revert_out_data = await step_class.revert(revert_in_context)

            await _push_output_context(step, runs_store_repo, revert_out_data, step_class.revert_provides_outputs())
        else:
            apply_in_context = await _get_input_context(app, step, runs_store_repo, step_class.apply_requests_inputs())
            apply_out_data = await step_class.apply(apply_in_context)

            await _push_output_context(step, runs_store_repo, apply_out_data, step_class.apply_provides_outputs())
    finally:
        # always emit event that step finished regardless of errors
        await interrupt_queue.put(_InterruptReasson.STEP_COMPLETED)


async def _task_lease_heartbeat(
    app: FastAPI,
    interrupt_queue: Queue[_InterruptReasson],
    cancellation_notifier: ChangeNotifier,
    step_id: StepId,
    worker_id: WorkerId,
) -> None:
    steps_lease_repo = get_repository(app, StepsLeaseRepository)
    lease_extended = await steps_lease_repo.acquire_or_extend_lease(step_id, worker_id)
    if not lease_extended:
        await cancellation_notifier.notify(step_id)
        await interrupt_queue.put(_InterruptReasson.LEASE_EXPIRY)


async def _handler_step_cancellation(
    interrupt_queue: Queue[_InterruptReasson], step_id: StepId, step_id_to_cancel: StepId
) -> None:
    if step_id_to_cancel == step_id:
        await interrupt_queue.put(_InterruptReasson.USER_CANCELLATION_REQUESTED)


async def _try_handle_step(
    app: FastAPI,
    cancellation_notifier: ChangeNotifier,
    worker_id: WorkerId,
    *,
    heartbeat_interval: timedelta,
    search_step_id: StepId | None,
) -> None:
    """tries to acquire one step at a time, if it succeeds then it starts processing"""

    # 1. try to acquire a job from the queue (or quit loop if none is available)
    steps_repo = get_repository(app, StepsRepository)

    step = await steps_repo.get_step_for_worker(search_step_id)
    if step is None:
        return

    _logger.debug("worker picked up step_id=%s", step.step_id)

    interrupt_queue = Queue[_InterruptReasson]()

    # 2. start task for lease extension (can also issue a cancellation if lease expired)

    lease_task = create_periodic_task(
        _task_lease_heartbeat,
        interval=heartbeat_interval,
        task_name=f"_lease_heartbeat_step_{step.step_id}",
        app=app,
        interrupt_queue=interrupt_queue,
        cancellation_notifier=cancellation_notifier,
        step_id=step.step_id,
        worker_id=worker_id,
    )

    # 3. start background task for cancellation monitoring
    handler_step_cancellation = partial(_handler_step_cancellation, interrupt_queue, step.step_id)

    await cancellation_notifier.subscribe(handler_step_cancellation)
    # 4. start background task that runs the user's payload

    step_runner_task = create_task(
        _task_step_runner(app, step, interrupt_queue), name=f"_step_runner_step_{step.step_id}"
    )

    # 5. wait for cancellation or payload completion or cancellation due to lease expiry
    try:
        interrupt_reason: _InterruptReasson | None = None

        # wait for the result to finish
        with suppress(asyncio.TimeoutError):
            interrupt_reason = await asyncio.wait_for(interrupt_queue.get(), timeout=step.timeout.total_seconds())

        match interrupt_reason:
            case _InterruptReasson.USER_CANCELLATION_REQUESTED | _InterruptReasson.LEASE_EXPIRY | None:
                await cancel_wait_task(step_runner_task)
                await steps_repo.step_cancelled(step.step_id)

                _logger.info(
                    "step_id=%s interrupted because: %s",
                    step.step_id,
                    interrupt_reason if interrupt_reason else f"timed out after {step.timeout=}",
                )
            case _InterruptReasson.STEP_COMPLETED:
                try:
                    await step_runner_task
                    await steps_repo.step_finished_successfully(step.step_id)
                except Exception as e:  # pylint: disable=broad-except
                    _logger.exception("step_id=%s failed", step.step_id)

                    fail_message = create_troubleshooting_log_message(
                        user_error_msg=f"step_id={step.step_id} failed", error=e
                    )
                    await steps_repo.step_finished_with_failure(step.step_id, fail_message)
    finally:
        await cancel_wait_task(lease_task)
        await cancellation_notifier.unsubscribe(handler_step_cancellation)


_NAME: Final[str] = "scheduler_worker_manager"


class WorkerManager(SingletonInAppStateMixin, SupportsLifecycle):
    app_state_name: str = f"p_{_NAME}"

    def __init__(
        self,
        app: FastAPI,
        check_for_steps_interval: timedelta,
        queue_consumer_expected_runtime_duration: timedelta,
        heartbeat_interval: timedelta,
        queue_max_burst: NonNegativeInt,
    ) -> None:
        self.app = app
        self.check_for_steps_interval = check_for_steps_interval
        self.heartbeat_interval = heartbeat_interval

        self._cancellation_notifier = ChangeNotifier()

        self._consumer_count = get_consumer_count(queue_consumer_expected_runtime_duration, queue_max_burst)
        _logger.info("worker queue consumers count=%s", self._consumer_count)
        self._queue: BoundedPubSubQueue[StepId | None] = BoundedPubSubQueue(maxsize=self._consumer_count)

        self._task_check_fro_steps: Task | None = None

    @cached_property
    def _notifications_manager(self) -> NotificationsManager:
        return NotificationsManager.get_from_app_state(self.app)

    @cached_property
    def _metrics_manager(self) -> MetricsManager:
        return MetricsManager.get_from_app_state(self.app)

    async def _safe_try_handle_step(self, worker_id: WorkerId, step_id: StepId | None) -> None:
        with log_context(_logger, logging.DEBUG, "handling step_id='%s'", step_id):
            try:
                await _try_handle_step(
                    self.app,
                    self._cancellation_notifier,
                    worker_id,
                    heartbeat_interval=self.heartbeat_interval,
                    search_step_id=step_id,
                )
            except Exception:
                self._metrics_manager.inc_worker_failures()
                raise

    async def _publish_to_queue(self) -> None:
        try:
            await self._queue.put(None)
        except QueueFull:
            self._metrics_manager.inc_dropped_worker_requests()
            _logger.warning("worker queue is full, dropping request on worker=%s", id(self.app))

    async def _handle_step_ready_notification(self, message: StepId) -> None:
        _ = message
        await self._publish_to_queue()

    async def _handle_step_cancelled_notification(self, message: StepId) -> None:
        await self._cancellation_notifier.notify(message)

    async def setup(self) -> None:
        for k in range(self._consumer_count):
            self._queue.subscribe(partial(self._safe_try_handle_step, f"worker-{k}-{uuid4()}"))

        self._notifications_manager.subscribe_handler(
            routing_key=RK_STEP_READY, handler=self._handle_step_ready_notification
        )

        self._notifications_manager.subscribe_handler(
            routing_key=RK_STEP_CANCELLED, handler=self._handle_step_cancelled_notification
        )

        @periodic(interval=self.check_for_steps_interval)
        async def _check_for_steps() -> None:
            # periodically enqueue a request to try and pickup requests which could be stuck
            await self._publish_to_queue()

        self._task_check_fro_steps = create_task(_check_for_steps(), name=f"_periodic_{_NAME}_check_fro_steps")

    async def shutdown(self) -> None:
        if self._task_check_fro_steps is not None:
            await cancel_wait_task(self._task_check_fro_steps)

        await self._queue.close()
