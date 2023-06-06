import logging
from abc import abstractmethod
from asyncio import Future, Queue, Task, create_task, wait_for
from dataclasses import dataclass
from typing import Any, Final

from .background_task import cancel_task
from .logging_utils import log_context

_logger = logging.getLogger(__name__)

_CANCEL_TASK_TIMEOUT_S: Final[float] = 5


@dataclass
class _Request:
    future: Future
    args: tuple[Any]
    kwargs: dict[str, Any]


class BaseSerialExecutor:
    def __init__(self) -> None:
        self._queue: Queue[_Request | None] = Queue()
        self._worker_task: Task | None = None

    async def _worker(self) -> None:
        with log_context(
            _logger, logging.DEBUG, f"background processor for {self.__class__}"
        ):
            while True:
                request: _Request | None = await self._queue.get()
                if request is None:
                    break

                try:
                    request.future.set_result(
                        await self.run(*request.args, **request.kwargs)
                    )
                except Exception as e:  # pylint: disable=broad-exception-caught
                    request.future.set_exception(e)

    async def start(self):
        self._worker_task = create_task(self._worker())

    async def stop(self):
        if self._worker_task:
            await self._queue.put(None)
            await cancel_task(self._worker_task, timeout=_CANCEL_TASK_TIMEOUT_S)

    async def wait_for_result(self, *args: Any, timeout: float, **kwargs: Any) -> Any:
        """
        Guarantees that only one instance of `run` is triggered at a time and returns
        its result.
        If `run` raises an error that same error is raised in the context where this
        method is called.

        params:
            timeout: float seconds before giving up on waiting gor the result

        raises:
            asyncio.TimeoutError: if no result is provided after timeout seconds have massed
        """
        future = Future()
        request = _Request(future=future, args=args, kwargs=kwargs)
        await self._queue.put(request)

        # NOTE: this raises TimeoutError which has to be handled by tha caller
        await wait_for(future, timeout=timeout)

        # NOTE: will raise an exception if the future has raised na exception
        # This also has to be handled by the caller
        result = future.result()

        return result

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """code to be executed for each request"""
