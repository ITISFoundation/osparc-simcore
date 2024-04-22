import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable, Iterable
from datetime import timedelta
from enum import auto
from typing import Any, Final

import arrow
from faststream.exceptions import NackMessage, RejectMessage
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitRouter
from models_library.utils.enums import StrAutoEnum
from pydantic import NonNegativeInt
from servicelib.logging_utils import log_context
from servicelib.redis import RedisClientSDKHealthChecked
from settings_library.rabbit import RabbitSettings

from ._base_deferred_handler import (
    BaseDeferredHandler,
    DeferredManagerContext,
    FullStartContext,
    UserStartContext,
)
from ._base_memory_manager import BaseMemoryManager
from ._models import (
    ClassUniqueReference,
    TaskResultCancelledError,
    TaskResultError,
    TaskResultSuccess,
    TaskUID,
)
from ._redis_memory_manager import RedisMemoryManager
from ._task_schedule import TaskSchedule, TaskState
from ._utils import stop_retry_for_unintended_errors
from ._worker_tracker import WorkerTracker

_logger = logging.getLogger(__name__)

_DEFAULT_DEFERRED_MANAGER_WORKER_SLOTS: Final[NonNegativeInt] = 100
_DEFAULT_DELAY_BEFORE_NACK: Final[timedelta] = timedelta(seconds=1)


class _FastStreamRabbitQueue(StrAutoEnum):
    SCHEDULED = auto()
    SUBMIT_TASK = auto()
    WORKER = auto()

    ERROR_RESULT = auto()

    FINISHED_WITH_ERROR = auto()
    DEFERRED_RESULT = auto()
    CANCEL_DEFERRED = auto()


class _PatchStartDeferred:
    def __init__(
        self,
        *,
        class_unique_reference: ClassUniqueReference,
        handler_to_invoke: Callable[..., Awaitable[UserStartContext]],
        manager_schedule_deferred: Callable[
            [ClassUniqueReference, UserStartContext], Awaitable[None]
        ],
    ):
        self.class_unique_reference = class_unique_reference
        self.handler_to_invoke = handler_to_invoke
        self.manager_schedule_deferred = manager_schedule_deferred

    async def __call__(self, **kwargs) -> None:
        result: UserStartContext = await self.handler_to_invoke(**kwargs)
        await self.manager_schedule_deferred(self.class_unique_reference, result)


class _PatchCancelDeferred:
    def __init__(
        self,
        *,
        class_unique_reference: ClassUniqueReference,
        manager_cancel_deferred: Callable[[TaskUID], Awaitable[None]],
    ) -> None:
        self.class_unique_reference = class_unique_reference
        self.manager_cancel_deferred = manager_cancel_deferred

    async def __call__(self, task_uid: TaskUID) -> None:
        await self.manager_cancel_deferred(task_uid)


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
        scheduler_redis_sdk: RedisClientSDKHealthChecked,
        *,
        globals_for_start_context: DeferredManagerContext,
        max_workers: NonNegativeInt = _DEFAULT_DEFERRED_MANAGER_WORKER_SLOTS,
        delay_when_requeuing_message: timedelta = _DEFAULT_DELAY_BEFORE_NACK,
    ) -> None:

        self._memory_manager: BaseMemoryManager = RedisMemoryManager(
            scheduler_redis_sdk
        )

        self._worker_tracker = WorkerTracker(max_workers)
        self.delay_when_requeuing_message = delay_when_requeuing_message

        self.globals_for_start_context = globals_for_start_context

        self._patched_deferred_handlers: dict[
            ClassUniqueReference, type[BaseDeferredHandler]
        ] = {}

        self.broker: RabbitBroker = RabbitBroker(rabbit_settings.dsn)
        self.router: RabbitRouter = RabbitRouter()

        # NOTE: do not move this to a function, must remain in constructor
        # otherwise the calling_module will be this one instead of the actual one
        calling_module_name = inspect.getmodule(inspect.stack()[1][0]).__name__  # type: ignore

        # NOTE: RabbitMQ queues and exchanges are prefix by this
        self._global_resources_prefix = f"{calling_module_name}"

        self.common_exchange = RabbitExchange(
            f"{self._global_resources_prefix}_common", type=ExchangeType.DIRECT
        )
        self.cancellation_exchange = RabbitExchange(
            f"{self._global_resources_prefix}_cancellation", type=ExchangeType.FANOUT
        )

    def register_based_deferred_handlers(self) -> None:
        """Allows subclasses of ``BaseDeferredHandler`` to be scheduled.

        NOTE: If a new subclass of ``BaseDeferredHandler`` was defined after
        the call to ``Scheduler.setup()`` this should be called to allow for
        scheduling.
        """
        for subclass in BaseDeferredHandler.SUBCLASSES:
            class_unique_reference: ClassUniqueReference = (
                subclass.get_class_unique_reference()
            )

            _logger.debug("Patching `start_deferred` for %s", class_unique_reference)
            patched_start_deferred = _PatchStartDeferred(
                class_unique_reference=class_unique_reference,
                handler_to_invoke=subclass.start_deferred,
                manager_schedule_deferred=self.__start_deferred,
            )
            subclass.start_deferred = patched_start_deferred  # type: ignore

            _logger.debug("Patching `cancel_deferred` for %s", class_unique_reference)
            patched_cancel_deferred = _PatchCancelDeferred(
                class_unique_reference=class_unique_reference,
                manager_cancel_deferred=self.__cancel_deferred,
            )
            subclass.cancel_deferred = patched_cancel_deferred  # type: ignore

            self._patched_deferred_handlers[class_unique_reference] = subclass

    def _get_global_queue_name(self, queue_name: _FastStreamRabbitQueue) -> str:
        return f"{self._global_resources_prefix}_{queue_name}"

    def __get_subclass(
        self, class_unique_reference: ClassUniqueReference
    ) -> type[BaseDeferredHandler]:
        return self._patched_deferred_handlers[class_unique_reference]

    async def __start_deferred(
        self,
        class_unique_reference: ClassUniqueReference,
        user_start_context: UserStartContext,
    ) -> None:
        """Assembles TaskSchedule stores it and starts the scheduling chain"""
        # NOTE: this is used internally but triggered by when calling `BaseDeferredHandler.start_deferred`

        _logger.debug(
            "Scheduling '%s' with payload '%s'",
            class_unique_reference,
            user_start_context,
        )

        task_uid = await self._memory_manager.get_task_unique_identifier()
        subclass = self.__get_subclass(class_unique_reference)
        full_start_context = self.__get_start_context(user_start_context)

        task_schedule = TaskSchedule(
            timeout=await subclass.get_timeout(full_start_context),
            remaining_retries=await subclass.get_retries(full_start_context),
            class_unique_reference=class_unique_reference,
            user_start_context=user_start_context,
            state=TaskState.SCHEDULED,
        )

        await self._memory_manager.save(task_uid, task_schedule)
        _logger.debug("Scheduled task '%s' with entry: %s", task_uid, task_schedule)
        await self.broker.publish(
            task_uid,
            queue=self._get_global_queue_name(_FastStreamRabbitQueue.SCHEDULED),
            exchange=self.common_exchange,
        )

        await subclass.on_deferred_created(task_uid)

    async def __get_task_schedule(
        self, task_uid: TaskUID, *, expected_state: TaskState
    ) -> TaskSchedule:
        task_schedule = await self._memory_manager.get(task_uid)

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
            msg = f"Detected unexpected state '{task_schedule.state}', should be: '{expected_state}'"
            raise RuntimeError(msg)

        return task_schedule

    def __get_start_context(
        self, user_start_context: UserStartContext
    ) -> FullStartContext:
        return {**self.globals_for_start_context, **user_start_context}

    @stop_retry_for_unintended_errors
    async def _fs_handle_scheduled(  # pylint:disable=method-hidden
        self, task_uid: TaskUID
    ) -> None:

        _log_state(TaskState.SCHEDULED, task_uid)

        task_schedule = await self.__get_task_schedule(
            task_uid, expected_state=TaskState.SCHEDULED
        )

        task_schedule.state = TaskState.SUBMIT_TASK
        await self._memory_manager.save(task_uid, task_schedule)

        await self.broker.publish(
            task_uid,
            queue=self._get_global_queue_name(_FastStreamRabbitQueue.SUBMIT_TASK),
            exchange=self.common_exchange,
        )

    @stop_retry_for_unintended_errors
    async def _fs_handle_submit_task(  # pylint:disable=method-hidden
        self, task_uid: TaskUID
    ) -> None:
        _log_state(TaskState.SUBMIT_TASK, task_uid)

        task_schedule = await self.__get_task_schedule(
            task_uid, expected_state=TaskState.SUBMIT_TASK
        )
        task_schedule.remaining_retries -= 1
        task_schedule.state = TaskState.WORKER
        await self._memory_manager.save(task_uid, task_schedule)

        await self.broker.publish(
            task_uid,
            queue=self._get_global_queue_name(_FastStreamRabbitQueue.WORKER),
            exchange=self.common_exchange,
        )

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
                full_start_context = self.__get_start_context(
                    task_schedule.user_start_context
                )
                task_schedule.result = await self._worker_tracker.handle_run_deferred(
                    subclass, task_uid, full_start_context, task_schedule.timeout
                )

        _logger.debug(
            "Worker for task_uid '%s' produced result=%s",
            task_uid,
            f"{task_schedule.result}",
        )

        if isinstance(task_schedule.result, TaskResultSuccess):
            task_schedule.state = TaskState.DEFERRED_RESULT
            await self._memory_manager.save(task_uid, task_schedule)
            await self.broker.publish(
                task_uid,
                queue=self._get_global_queue_name(
                    _FastStreamRabbitQueue.DEFERRED_RESULT
                ),
                exchange=self.common_exchange,
            )
            return

        if isinstance(task_schedule.result, TaskResultError | TaskResultCancelledError):
            task_schedule.state = TaskState.ERROR_RESULT
            await self._memory_manager.save(task_uid, task_schedule)
            await self.broker.publish(
                task_uid,
                queue=self._get_global_queue_name(_FastStreamRabbitQueue.ERROR_RESULT),
                exchange=self.common_exchange,
            )
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

        if task_schedule.remaining_retries > 0 and not isinstance(
            task_schedule.result, TaskResultCancelledError
        ):
            _logger.debug("Schedule retry attempt for task_uid '%s'", task_uid)
            # does not retry if task was cancelled
            task_schedule.state = TaskState.SUBMIT_TASK
            await self._memory_manager.save(task_uid, task_schedule)
            await self.broker.publish(
                task_uid,
                queue=self._get_global_queue_name(_FastStreamRabbitQueue.SUBMIT_TASK),
                exchange=self.common_exchange,
            )
            return

        task_schedule.state = TaskState.FINISHED_WITH_ERROR
        await self._memory_manager.save(task_uid, task_schedule)
        await self.broker.publish(
            task_uid,
            queue=self._get_global_queue_name(
                _FastStreamRabbitQueue.FINISHED_WITH_ERROR
            ),
            exchange=self.common_exchange,
        )

    async def __remove_task(
        self, task_uid: TaskUID, task_schedule: TaskSchedule
    ) -> None:
        _logger.info(
            "Finished handling of '%s' in %s",
            task_schedule.class_unique_reference,
            arrow.utcnow().datetime - task_schedule.time_started,
        )
        _logger.debug("Removing task %s", task_uid)
        await self._memory_manager.remove(task_uid)

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
            start_context = self.__get_start_context(task_schedule.user_start_context)
            await subclass.on_finished_with_error(task_schedule.result, start_context)
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
        start_context = self.__get_start_context(task_schedule.user_start_context)
        assert isinstance(task_schedule.result, TaskResultSuccess)  # nosec
        await subclass.on_deferred_result(task_schedule.result.value, start_context)

        await self.__remove_task(task_uid, task_schedule)

    async def __cancel_deferred(self, task_uid: TaskUID) -> None:
        task_schedule: TaskSchedule | None = await self._memory_manager.get(task_uid)
        if task_schedule is None:
            _logger.warning("No entry four to cancel found for task_uid '%s'", task_uid)
            return

        _logger.info("Attempting to cancel task_uid '%s'", task_uid)
        task_schedule.state = TaskState.MANUALLY_CANCELLED
        await self._memory_manager.save(task_uid, task_schedule)

        await self.broker.publish(
            task_uid,
            queue=self._get_global_queue_name(_FastStreamRabbitQueue.CANCEL_DEFERRED),
            exchange=self.cancellation_exchange,
        )

    @stop_retry_for_unintended_errors
    async def _fs_handle_cancel_deferred(  # pylint:disable=method-hidden
        self, task_uid: TaskUID
    ) -> None:
        _log_state(TaskState.MANUALLY_CANCELLED, task_uid)
        _logger.info("Attempting to cancel task_uid '%s'", task_uid)

        task_schedule = await self.__get_task_schedule(
            task_uid, expected_state=TaskState.MANUALLY_CANCELLED
        )

        if task_schedule.state == TaskState.WORKER:
            run_was_cancelled = self._worker_tracker.cancel_run_deferred(task_uid)
            if not run_was_cancelled:
                _logger.debug(
                    "Currently not handling task related to '%s'. Did not cancel it.",
                    task_uid,
                )
                return

        _logger.info("Found and cancelled run_deferred for '%s'", task_uid)
        await self.__remove_task(task_uid, task_schedule)

    def _register_subscribers(self) -> None:
        # Registers subscribers at runtime instead of import time.
        # Enables for code reuse.

        # pylint:disable=unexpected-keyword-arg
        # pylint:disable=no-value-for-parameter
        self._fs_handle_scheduled = self.router.subscriber(
            queue=self._get_global_queue_name(_FastStreamRabbitQueue.SCHEDULED),
            exchange=self.common_exchange,
            retry=True,
        )(self._fs_handle_scheduled)

        self._fs_handle_submit_task = self.router.subscriber(
            queue=self._get_global_queue_name(_FastStreamRabbitQueue.SUBMIT_TASK),
            exchange=self.common_exchange,
            retry=True,
        )(self._fs_handle_submit_task)

        self._fs_handle_worker = self.router.subscriber(
            queue=self._get_global_queue_name(_FastStreamRabbitQueue.WORKER),
            exchange=self.common_exchange,
            retry=True,
        )(self._fs_handle_worker)

        self._fs_handle_error_result = self.router.subscriber(
            queue=self._get_global_queue_name(_FastStreamRabbitQueue.ERROR_RESULT),
            exchange=self.common_exchange,
            retry=True,
        )(self._fs_handle_error_result)

        self._fs_handle_finished_with_error = self.router.subscriber(
            queue=self._get_global_queue_name(
                _FastStreamRabbitQueue.FINISHED_WITH_ERROR
            ),
            exchange=self.common_exchange,
            retry=True,
        )(self._fs_handle_finished_with_error)

        self._fs_handle_deferred_result = self.router.subscriber(
            queue=self._get_global_queue_name(_FastStreamRabbitQueue.DEFERRED_RESULT),
            exchange=self.common_exchange,
            retry=True,
        )(self._fs_handle_deferred_result)

        self._fs_handle_cancel_deferred = self.router.subscriber(
            queue=self._get_global_queue_name(_FastStreamRabbitQueue.CANCEL_DEFERRED),
            exchange=self.cancellation_exchange,
            retry=True,
        )(self._fs_handle_cancel_deferred)

    async def setup(self) -> None:
        self._register_subscribers()
        self.broker.include_router(self.router)

        self.register_based_deferred_handlers()

        await self.broker.start()

    async def shutdown(self) -> None:
        await self.broker.close()
