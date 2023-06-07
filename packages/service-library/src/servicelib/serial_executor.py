import asyncio
import functools
import logging
from abc import abstractmethod
from asyncio import Future, Queue, Task, create_task, wait_for
from dataclasses import dataclass
from typing import Any, Final, TypeAlias

from .background_task import cancel_task
from .logging_utils import log_context

_logger = logging.getLogger(__name__)

_CANCEL_TASK_TIMEOUT_S: Final[float] = 5

ContextKey: TypeAlias = str


@dataclass
class _Request:
    context_key: ContextKey
    future: Future
    args: tuple[Any]
    kwargs: dict[str, Any]


class BaseSerialExecutor:
    """
    If a bunch of wait_for_result operations are launched together,
    they are tried to be executed in parallel except the ones that have the same context_key.

    """

    def __init__(self, polling_interval: float = 0.1) -> None:
        self.polling_interval: float = polling_interval

        self._requests_queue: Queue[_Request | None] = Queue()
        self._request_ingestion_task: Task | None = None

        # TODO maybe a better name here?
        self._context_queue: Queue[int | None] = Queue()
        self._context_task: Task | None = None

        self._requests_to_start: dict[ContextKey, list[_Request]] = {}
        self._running_requests: dict[ContextKey, Task] = {}

    async def _handle_payload(self, request: _Request) -> None:
        try:
            request.future.set_result(await self.run(*request.args, **request.kwargs))
        except Exception as e:  # pylint: disable=broad-exception-caught
            request.future.set_exception(e)

    async def _request_processor_worker(self) -> None:
        with log_context(
            _logger, logging.DEBUG, f"request processor for {self.__class__}"
        ):
            while True:
                message: int | None = await self._context_queue.get()
                if message is None:
                    break

                # NOTE: this entry logs are supposed to stop after all
                # tasks for the context are processed
                _logger.debug("Received request to start a task")

                # find the next context_key that can be started
                found_context_key: ContextKey | None = None
                for context_key in self._requests_to_start:
                    if context_key not in self._running_requests:
                        found_context_key = context_key

                # if we expect any other jobs to be started do this
                if found_context_key is None and len(self._requests_to_start) != 0:
                    # waiting a bit to give time for the current task to finish
                    # before creating a new one
                    await asyncio.sleep(self.polling_interval)
                    await self._context_queue.put(1)  # trigger
                    continue

                if found_context_key is None:
                    _logger.debug("Done processing enqueued requests")
                    continue

                # there are requests which can be picked up and started

                requests: list[_Request] = self._requests_to_start[found_context_key]
                request = requests.pop()

                self._running_requests[request.context_key] = create_task(
                    self._handle_payload(request)
                )
                self._running_requests[request.context_key].add_done_callback(
                    functools.partial(
                        lambda s, _: self._running_requests.pop(s, None),
                        request.context_key,
                    )
                )

    async def _request_ingestion_worker(self) -> None:
        with log_context(
            _logger, logging.DEBUG, f"request ingestion for {self.__class__}"
        ):
            while True:
                request: _Request | None = await self._requests_queue.get()
                if request is None:
                    break

                if request.context_key not in self._requests_to_start:
                    self._requests_to_start[request.context_key] = []
                self._requests_to_start[request.context_key].append(request)

                await self._context_queue.put(1)  # trigger

    async def start(self):
        self._request_ingestion_task = create_task(self._request_ingestion_worker())
        self._context_task = create_task(self._request_processor_worker())

    async def stop(self):
        if self._request_ingestion_task:
            await self._requests_queue.put(None)
            await cancel_task(
                self._request_ingestion_task, timeout=_CANCEL_TASK_TIMEOUT_S
            )
        if self._context_task:
            await self._context_queue.put(None)
            await cancel_task(self._context_task, timeout=_CANCEL_TASK_TIMEOUT_S)

        # cancel all existing tasks
        for task in tuple(self._running_requests.values()):
            await cancel_task(task, timeout=_CANCEL_TASK_TIMEOUT_S)

    async def wait_for_result(
        self, *args: Any, context_key: ContextKey, timeout: float, **kwargs: Any
    ) -> Any:
        """
        Starts task and executes the code defined by `run`, waits for the task to
        finish and returns its result.
        All calls in parallel with the same `context_key` will get executed
        sequentially. It guarantees only one task with the same `context_key`
        is active at the same time.

        If `run` raises an error that same error is raised in the context where this
        method is called.

        params:
            context_key: calls sharing the same `context_key` will be ran in sequence,
                all others will be ran in parallel
            timeout: float seconds before giving up on waiting gor the result;
                needs to take into consideration the fact that other tasks might be already
                started for the same `context_key`, before those are finished this request
                will not execute

        raises:
            asyncio.TimeoutError: if no result is provided after timeout seconds have massed
        """
        future = Future()
        request = _Request(
            context_key=context_key, future=future, args=args, kwargs=kwargs
        )
        await self._requests_queue.put(request)

        # NOTE: this raises TimeoutError which has to be handled by tha caller
        await wait_for(future, timeout=timeout)

        # NOTE: will raise an exception if the future has raised na exception
        # This also has to be handled by the caller
        result = future.result()

        return result

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """code to be executed for each request"""
