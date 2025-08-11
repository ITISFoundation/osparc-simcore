import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable, Iterable
from datetime import timedelta
from enum import Enum
from typing import Any, Final

import arrow
from faststream.exceptions import NackMessage, RejectMessage
from faststream.rabbit import (
    ExchangeType,
    RabbitBroker,
    RabbitExchange,
    RabbitQueue,
    RabbitRouter,
)
from pydantic import NonNegativeInt
from settings_library.rabbit import RabbitSettings

from ..logging_utils import log_catch, log_context
from ..redis import RedisClientSDK
from ._base_deferred_handler import (
    BaseDeferredHandler,
    DeferredContext,
    GlobalsContext,
    StartContext,
)
from ._base_task_tracker import BaseTaskTracker
from ._models import (
    ClassUniqueReference,
    TaskResultCancelledError,
    TaskResultError,
    TaskResultSuccess,
    TaskUID,
)
from ._redis_task_tracker import RedisTaskTracker
from ._task_schedule import TaskScheduleModel, TaskState
from ._utils import stop_retry_for_unintended_errors
from ._worker_tracker import WorkerTracker

_logger = logging.getLogger(__name__)

_DEFAULT_DEFERRED_MANAGER_WORKER_SLOTS: Final[NonNegativeInt] = 100
_DEFAULT_DELAY_BEFORE_NACK: Final[timedelta] = timedelta(seconds=1)


class _FastStreamRabbitQueue(str, Enum):
    SCHEDULED = "SCHEDULED"
    SUBMIT_TASK = "SUBMIT_TASK"
    WORKER = "WORKER"

    ERROR_RESULT = "ERROR_RESULT"

    FINISHED_WITH_ERROR = "FINISHED_WITH_ERROR"
    DEFERRED_RESULT = "DEFERRED_RESULT"
    MANUALLY_CANCELLED = "MANUALLY_CANCELLED"


def _get_queue_from_state(task_state: TaskState) -> _FastStreamRabbitQueue:
    return _FastStreamRabbitQueue(task_state)


class _PatchStartDeferred:
    def __init__(
        self,
        *,
        class_unique_reference: ClassUniqueReference,
        original_start: Callable[..., Awaitable[StartContext]],
        manager_schedule_deferred: Callable[
            [ClassUniqueReference, StartContext], Awaitable[None]
        ],
    ):
        self.class_unique_reference = class_unique_reference
        self.original_start = original_start
        self.manager_schedule_deferred = manager_schedule_deferred

    async def __call__(self, **kwargs) -> None:
        result: StartContext = await self.original_start(**kwargs)
        await self.manager_schedule_deferred(self.class_unique_reference, result)


class _PatchCancelDeferred:
    def __init__(
        self,
        *,
        original_cancel: Callable[[TaskUID], Awaitable[None]],
        manager_cancel: Callable[[TaskUID], Awaitable[None]],
    ) -> None:
        self.original_cancel = original_cancel
        self.manager_cancel = manager_cancel

    async def __call__(self, task_uid: TaskUID) -> None:
        await self.manager_cancel(task_uid)


class _PatchIsPresent:
    def __init__(
        self,
        *,
        original_is_present: Callable[[TaskUID], Awaitable[bool]],
        manager_is_present: Callable[[TaskUID], Awaitable[bool]],
    ) -> None:
        self.original_is_present = original_is_present
        self.manager_is_present = manager_is_present

    async def __call__(self, task_uid: TaskUID) -> bool:
        return await self.manager_is_present(task_uid)


def _log_state(task_state: TaskState, task_uid: TaskUID) -> None:
    _logger.debug("Handling state '%s' for task_uid '%s'", task_state, task_uid)


def _raise_if_not_type(task_result: Any, expected_types: Iterable[type]) -> None:
    if not isinstance(task_result, tuple(expected_types)):
        msg = f"Unexpected '{task_result=}', should be one of {[x.__name__ for x in expected_types]}"
        raise TypeError(msg)


class DeferredManager:  # pylint:disable=too-many-instance-attributes
    def __init__(
        self,
        rabbit_settings: RabbitSettings,
        scheduler_redis_sdk: RedisClientSDK,
        *,
        globals_context: GlobalsContext,
        max_workers: NonNegativeInt = _DEFAULT_DEFERRED_MANAGER_WORKER_SLOTS,
        delay_when_requeuing_message: timedelta = _DEFAULT_DELAY_BEFORE_NACK,
    ) -> None:

        self._task_tracker: BaseTaskTracker = RedisTaskTracker(scheduler_redis_sdk)

        self._worker_tracker = WorkerTracker(max_workers)
        self.delay_when_requeuing_message = delay_when_requeuing_message

        self.globals_context = globals_context

        self._patched_deferred_handlers: dict[
            ClassUniqueReference, type[BaseDeferredHandler]
        ] = {}

        self.broker: RabbitBroker = RabbitBroker(
            rabbit_settings.dsn, log_level=logging.DEBUG
        )
        self.router: RabbitRouter = RabbitRouter()

        # NOTE: do not move this to a function, must remain in constructor
        # otherwise the calling_module will be this one instead of the actual one
        calling_module = inspect.getmodule(inspect.stack()[1][0])
        assert calling_module  # nosec
        calling_module_name = calling_module.__name__

        # NOTE: RabbitMQ queues and exchanges are prefix by this
        self._global_resources_prefix = f"{calling_module_name}"

        self.common_exchange = RabbitExchange(
            f"{self._global_resources_prefix}_common",
            durable=True,
            type=ExchangeType.DIRECT,
        )
        self.cancellation_exchange = RabbitExchange(
            f"{self._global_resources_prefix}_cancellation",
            durable=True,
            type=ExchangeType.FANOUT,
        )

    def patch_based_deferred_handlers(self) -> None:
        """Allows subclasses of ``BaseDeferredHandler`` to be scheduled.

        NOTE: If a new subclass of ``BaseDeferredHandler`` was defined after
        the call to ``Scheduler.setup()`` this should be called to allow for
        scheduling.
        """
        # pylint:disable=protected-access
        for subclass in BaseDeferredHandler._SUBCLASSES:  # noqa: SLF001
            class_unique_reference: ClassUniqueReference = (
                subclass._get_class_unique_reference()  # noqa: SLF001
            )

            if not isinstance(subclass.start, _PatchStartDeferred):
                with log_context(
                    _logger,
                    logging.DEBUG,
                    f"Patch `start` for {class_unique_reference}",
                ):
                    patched_start = _PatchStartDeferred(
                        class_unique_reference=class_unique_reference,
                        original_start=subclass.start,
                        manager_schedule_deferred=self.__start,
                    )
                    subclass.start = patched_start  # type: ignore

            if not isinstance(subclass.cancel, _PatchCancelDeferred):
                with log_context(
                    _logger,
                    logging.DEBUG,
                    f"Patch `cancel` for {class_unique_reference}",
                ):
                    patched_cancel = _PatchCancelDeferred(
                        original_cancel=subclass.cancel,
                        manager_cancel=self.__cancel,
                    )
                    subclass.cancel = patched_cancel  # type: ignore

            if not isinstance(subclass.is_present, _PatchIsPresent):
                with log_context(
                    _logger,
                    logging.DEBUG,
                    f"Patch `is_present` for {class_unique_reference}",
                ):
                    patched_is_present = _PatchIsPresent(
                        original_is_present=subclass.is_present,
                        manager_is_present=self.__is_present,
                    )
                    subclass.is_present = patched_is_present  # type: ignore

            self._patched_deferred_handlers[class_unique_reference] = subclass

    @classmethod
    def un_patch_base_deferred_handlers(cls) -> None:
        # pylint:disable=protected-access
        for subclass in BaseDeferredHandler._SUBCLASSES:  # noqa: SLF001
            class_unique_reference: ClassUniqueReference = (
                subclass._get_class_unique_reference()  # noqa: SLF001
            )

            if isinstance(subclass.start, _PatchStartDeferred):
                with log_context(
                    _logger,
                    logging.DEBUG,
                    f"Remove `start` patch for {class_unique_reference}",
                ):
                    subclass.start = subclass.start.original_start

            if isinstance(subclass.cancel, _PatchCancelDeferred):
                with log_context(
                    _logger,
                    logging.DEBUG,
                    f"Remove `cancel` patch for {class_unique_reference}",
                ):
                    subclass.cancel = (  # type: ignore
                        subclass.cancel.original_cancel  # type: ignore
                    )

            if isinstance(subclass.is_present, _PatchIsPresent):
                with log_context(
                    _logger,
                    logging.DEBUG,
                    f"Remove `is_present` patch for {class_unique_reference}",
                ):
                    subclass.is_present = (  # type: ignore
                        subclass.is_present.original_is_present  # type: ignore
                    )

    def _get_global_queue(self, queue_name: _FastStreamRabbitQueue) -> RabbitQueue:
        return RabbitQueue(
            f"{self._global_resources_prefix}_{queue_name}", durable=True
        )

    def __get_subclass(
        self, class_unique_reference: ClassUniqueReference
    ) -> type[BaseDeferredHandler]:
        return self._patched_deferred_handlers[class_unique_reference]

    def __get_deferred_context(self, start_context: StartContext) -> DeferredContext:
        return {**self.globals_context, **start_context}

    async def __publish_to_queue(
        self, task_uid: TaskUID, queue: _FastStreamRabbitQueue
    ) -> None:
        await self.broker.publish(
            task_uid,
            queue=self._get_global_queue(queue),
            exchange=(
                self.cancellation_exchange
                if queue == _FastStreamRabbitQueue.MANUALLY_CANCELLED
                else self.common_exchange
            ),
        )

    async def __start(
        self,
        class_unique_reference: ClassUniqueReference,
        start_context: StartContext,
    ) -> None:
        """Assembles TaskSchedule stores it and starts the scheduling chain"""
        # NOTE: this is used internally but triggered by when calling `BaseDeferredHandler.start`

        _logger.debug(
            "Scheduling '%s' with payload '%s'",
            class_unique_reference,
            start_context,
        )

        task_uid = await self._task_tracker.get_new_unique_identifier()
        subclass = self.__get_subclass(class_unique_reference)
        deferred_context = self.__get_deferred_context(start_context)

        task_schedule = TaskScheduleModel(
            timeout=await subclass.get_timeout(deferred_context),
            execution_attempts=await subclass.get_retries(deferred_context) + 1,
            class_unique_reference=class_unique_reference,
            start_context=start_context,
            state=TaskState.SCHEDULED,
        )

        with log_catch(_logger, reraise=False):
            await subclass.on_created(task_uid, deferred_context)

        await self._task_tracker.save(task_uid, task_schedule)
        _logger.debug("Scheduled task '%s' with entry: %s", task_uid, task_schedule)
        await self.__publish_to_queue(task_uid, _FastStreamRabbitQueue.SCHEDULED)

    async def __get_task_schedule(
        self, task_uid: TaskUID, *, expected_state: TaskState
    ) -> TaskScheduleModel:
        task_schedule = await self._task_tracker.get(task_uid)

        if task_schedule is None:
            msg = f"Could not find a task_schedule for task_uid '{task_uid}'"
            raise RuntimeError(msg)

        if (
            task_schedule.state != expected_state
            and task_schedule.state == TaskState.MANUALLY_CANCELLED
        ):
            _logger.debug(
                "Detected that task_uid '%s' was cancelled. Skipping processing of %s",
                task_uid,
                expected_state,
            )
            # abandon message processing
            raise RejectMessage

        if task_schedule.state != expected_state:
            # NOTE: switching state is a two phase operation (commit to memory and trigger "next handler")
            # if there is an interruption between committing to memory and triggering the "next handler"
            # the old handler will be retried (this is by design and guarantees that the event chain is not interrupted)
            # It is safe to skip this event handling and trigger the next one

            _logger.debug(
                "Detected unexpected state '%s' for task '%s', should be: '%s'",
                task_schedule.state,
                task_uid,
                expected_state,
            )

            await self.__publish_to_queue(
                task_uid, _get_queue_from_state(task_schedule.state)
            )
            raise RejectMessage

        return task_schedule

    @stop_retry_for_unintended_errors
    async def _fs_handle_scheduled(  # pylint:disable=method-hidden
        self, task_uid: TaskUID
    ) -> None:

        _log_state(TaskState.SCHEDULED, task_uid)

        task_schedule = await self.__get_task_schedule(
            task_uid, expected_state=TaskState.SCHEDULED
        )

        task_schedule.state = TaskState.SUBMIT_TASK
        await self._task_tracker.save(task_uid, task_schedule)

        await self.__publish_to_queue(task_uid, _FastStreamRabbitQueue.SUBMIT_TASK)

    @stop_retry_for_unintended_errors
    async def _fs_handle_submit_task(  # pylint:disable=method-hidden
        self, task_uid: TaskUID
    ) -> None:
        _log_state(TaskState.SUBMIT_TASK, task_uid)

        task_schedule = await self.__get_task_schedule(
            task_uid, expected_state=TaskState.SUBMIT_TASK
        )
        task_schedule.execution_attempts -= 1
        task_schedule.state = TaskState.WORKER
        await self._task_tracker.save(task_uid, task_schedule)

        await self.__publish_to_queue(task_uid, _FastStreamRabbitQueue.WORKER)

    @stop_retry_for_unintended_errors
    async def _fs_handle_worker(  # pylint:disable=method-hidden
        self, task_uid: TaskUID
    ) -> None:
        _log_state(TaskState.WORKER, task_uid)

        if not self._worker_tracker.has_free_slots():
            # NOTE: puts the message back in rabbit for redelivery since this pool is currently busy
            _logger.info("All workers in pool are busy, requeuing job for %s", task_uid)
            # NOTE: due to a bug the message is resent to the same queue (same process)
            # to avoid picking it up immediately add sme delay
            # (for details see https://faststream.airt.ai/latest/rabbit/ack/#retries)
            await asyncio.sleep(self.delay_when_requeuing_message.total_seconds())
            raise NackMessage

        task_schedule = await self.__get_task_schedule(
            task_uid, expected_state=TaskState.WORKER
        )

        async with self._worker_tracker:
            with log_context(
                _logger,
                logging.DEBUG,
                f"Worker handling task_uid '{task_uid}' for {task_schedule}",
            ):
                subclass = self.__get_subclass(task_schedule.class_unique_reference)
                deferred_context = self.__get_deferred_context(
                    task_schedule.start_context
                )
                task_schedule.result = await self._worker_tracker.handle_run(
                    subclass, task_uid, deferred_context, task_schedule.timeout
                )

        _logger.debug(
            "Worker for task_uid '%s' produced result=%s",
            task_uid,
            f"{task_schedule.result}",
        )

        if isinstance(task_schedule.result, TaskResultSuccess):
            task_schedule.state = TaskState.DEFERRED_RESULT
            await self._task_tracker.save(task_uid, task_schedule)
            await self.__publish_to_queue(
                task_uid, _FastStreamRabbitQueue.DEFERRED_RESULT
            )
            return

        if isinstance(task_schedule.result, TaskResultError | TaskResultCancelledError):
            task_schedule.state = TaskState.ERROR_RESULT
            await self._task_tracker.save(task_uid, task_schedule)
            await self.__publish_to_queue(task_uid, _FastStreamRabbitQueue.ERROR_RESULT)
            return

        msg = (
            f"Unexpected state, result type={type(task_schedule.result)} should be an instance "
            f"of {TaskResultSuccess.__name__}, {TaskResultError.__name__} or {TaskResultCancelledError.__name__}"
        )
        raise TypeError(msg)

    @stop_retry_for_unintended_errors
    async def _fs_handle_error_result(  # pylint:disable=method-hidden
        self, task_uid: TaskUID
    ) -> None:
        _log_state(TaskState.ERROR_RESULT, task_uid)

        task_schedule = await self.__get_task_schedule(
            task_uid, expected_state=TaskState.ERROR_RESULT
        )
        _raise_if_not_type(
            task_schedule.result, (TaskResultError, TaskResultCancelledError)
        )

        if task_schedule.execution_attempts > 0 and not isinstance(
            task_schedule.result, TaskResultCancelledError
        ):
            _logger.debug("Schedule retry attempt for task_uid '%s'", task_uid)
            # does not retry if task was cancelled
            task_schedule.state = TaskState.SUBMIT_TASK
            await self._task_tracker.save(task_uid, task_schedule)
            await self.__publish_to_queue(task_uid, _FastStreamRabbitQueue.SUBMIT_TASK)
            return

        task_schedule.state = TaskState.FINISHED_WITH_ERROR
        await self._task_tracker.save(task_uid, task_schedule)
        await self.__publish_to_queue(
            task_uid, _FastStreamRabbitQueue.FINISHED_WITH_ERROR
        )

    async def __remove_task(
        self, task_uid: TaskUID, task_schedule: TaskScheduleModel
    ) -> None:
        _logger.info(
            "Finished handling of '%s' in %s",
            task_schedule.class_unique_reference,
            arrow.utcnow().datetime - task_schedule.time_started,
        )
        _logger.debug("Removing task %s", task_uid)
        await self._task_tracker.remove(task_uid)

    @stop_retry_for_unintended_errors
    async def _fs_handle_finished_with_error(  # pylint:disable=method-hidden
        self, task_uid: TaskUID
    ) -> None:
        _log_state(TaskState.FINISHED_WITH_ERROR, task_uid)

        task_schedule = await self.__get_task_schedule(
            task_uid, expected_state=TaskState.FINISHED_WITH_ERROR
        )
        _raise_if_not_type(
            task_schedule.result, (TaskResultError, TaskResultCancelledError)
        )

        if isinstance(task_schedule.result, TaskResultError):
            _logger.error(
                "Finished task_uid '%s' with error. See below for details.\n%s",
                task_uid,
                task_schedule.result.format_error(),
            )
            subclass = self.__get_subclass(task_schedule.class_unique_reference)
            deferred_context = self.__get_deferred_context(task_schedule.start_context)
            with log_catch(_logger, reraise=False):
                await subclass.on_finished_with_error(
                    task_schedule.result, deferred_context
                )
        else:
            _logger.debug("Task '%s' cancelled!", task_uid)

        await self.__remove_task(task_uid, task_schedule)

    @stop_retry_for_unintended_errors
    async def _fs_handle_deferred_result(  # pylint:disable=method-hidden
        self, task_uid: TaskUID
    ) -> None:
        _log_state(TaskState.DEFERRED_RESULT, task_uid)

        task_schedule = await self.__get_task_schedule(
            task_uid, expected_state=TaskState.DEFERRED_RESULT
        )
        _raise_if_not_type(task_schedule.result, (TaskResultSuccess,))

        subclass = self.__get_subclass(task_schedule.class_unique_reference)
        deferred_context = self.__get_deferred_context(task_schedule.start_context)
        assert isinstance(task_schedule.result, TaskResultSuccess)  # nosec

        with log_catch(_logger, reraise=False):
            await subclass.on_result(task_schedule.result.value, deferred_context)

        await self.__remove_task(task_uid, task_schedule)

    async def __cancel(self, task_uid: TaskUID) -> None:
        task_schedule: TaskScheduleModel | None = await self._task_tracker.get(task_uid)
        if task_schedule is None:
            _logger.warning("No entry four to cancel found for task_uid '%s'", task_uid)
            return

        _logger.info("Attempting to cancel task_uid '%s'", task_uid)
        task_schedule.state = TaskState.MANUALLY_CANCELLED
        await self._task_tracker.save(task_uid, task_schedule)

        await self.__publish_to_queue(
            task_uid, _FastStreamRabbitQueue.MANUALLY_CANCELLED
        )

    @stop_retry_for_unintended_errors
    async def _fs_handle_manually_cancelled(  # pylint:disable=method-hidden
        self, task_uid: TaskUID
    ) -> None:
        _log_state(TaskState.MANUALLY_CANCELLED, task_uid)
        _logger.info("Attempting to cancel task_uid '%s'", task_uid)

        task_schedule = await self.__get_task_schedule(
            task_uid, expected_state=TaskState.MANUALLY_CANCELLED
        )

        if task_schedule.state == TaskState.WORKER:
            run_was_cancelled = self._worker_tracker.cancel_run(task_uid)
            if not run_was_cancelled:
                _logger.debug(
                    "Currently not handling task related to '%s'. Did not cancel it.",
                    task_uid,
                )
                return

        _logger.info("Found and cancelled run for '%s'", task_uid)
        await self.__remove_task(task_uid, task_schedule)

    async def __is_present(self, task_uid: TaskUID) -> bool:
        task_schedule: TaskScheduleModel | None = await self._task_tracker.get(task_uid)
        return task_schedule is not None

    def _register_subscribers(self) -> None:
        # Registers subscribers at runtime instead of import time.
        # Enables code reuse.

        # pylint:disable=unexpected-keyword-arg
        # pylint:disable=no-value-for-parameter
        self._fs_handle_scheduled = self.router.subscriber(
            queue=self._get_global_queue(_FastStreamRabbitQueue.SCHEDULED),
            exchange=self.common_exchange,
            retry=True,
        )(self._fs_handle_scheduled)

        self._fs_handle_submit_task = self.router.subscriber(
            queue=self._get_global_queue(_FastStreamRabbitQueue.SUBMIT_TASK),
            exchange=self.common_exchange,
            retry=True,
        )(self._fs_handle_submit_task)

        self._fs_handle_worker = self.router.subscriber(
            queue=self._get_global_queue(_FastStreamRabbitQueue.WORKER),
            exchange=self.common_exchange,
            retry=True,
        )(self._fs_handle_worker)

        self._fs_handle_error_result = self.router.subscriber(
            queue=self._get_global_queue(_FastStreamRabbitQueue.ERROR_RESULT),
            exchange=self.common_exchange,
            retry=True,
        )(self._fs_handle_error_result)

        self._fs_handle_finished_with_error = self.router.subscriber(
            queue=self._get_global_queue(_FastStreamRabbitQueue.FINISHED_WITH_ERROR),
            exchange=self.common_exchange,
            retry=True,
        )(self._fs_handle_finished_with_error)

        self._fs_handle_deferred_result = self.router.subscriber(
            queue=self._get_global_queue(_FastStreamRabbitQueue.DEFERRED_RESULT),
            exchange=self.common_exchange,
            retry=True,
        )(self._fs_handle_deferred_result)

        self._fs_handle_manually_cancelled = self.router.subscriber(
            queue=self._get_global_queue(_FastStreamRabbitQueue.MANUALLY_CANCELLED),
            exchange=self.cancellation_exchange,
            retry=True,
        )(self._fs_handle_manually_cancelled)

    async def setup(self) -> None:
        self._register_subscribers()
        self.broker.include_router(self.router)

        self.patch_based_deferred_handlers()

        await self.broker.start()

    async def shutdown(self) -> None:
        self.un_patch_base_deferred_handlers()
        await self.broker.close()
