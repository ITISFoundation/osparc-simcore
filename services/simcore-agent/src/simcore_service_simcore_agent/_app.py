import asyncio
from collections import deque
import logging
import signal
import traceback
from contextlib import suppress
from typing import Any, Awaitable, Callable, Coroutine, Final, Optional

from pydantic import PositiveFloat, PositiveInt

from ._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG

logger = logging.getLogger(__name__)

DEFAULT_TASK_WAIT_ON_ERROR: Final[PositiveInt] = 10


class Application:
    HANDLED_EXIT_SIGNALS: set[signal.Signals] = {signal.SIGTERM, signal.SIGINT}

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        self._loop = asyncio.get_event_loop() if loop is None else loop
        for sig_name in self.HANDLED_EXIT_SIGNALS:
            self._loop.add_signal_handler(
                sig_name,
                lambda: self._loop.create_task(self._exit_gracefully(self._loop)),
            )

        self._keep_running: bool = True

        self._tasks: set[asyncio.Task] = set()
        self._coroutines: set[Coroutine] = set()
        self._registered_coroutines: set[str] = set()

    async def _exit_gracefully(self, loop: asyncio.AbstractEventLoop):
        async def _wat_for_task(task: asyncio.Task) -> None:
            with suppress(asyncio.CancelledError):
                await task

        tasks_to_wait: deque[Awaitable] = deque()
        for task in self._tasks:
            task.cancel()

            tasks_to_wait.append(_wat_for_task(task))

        await asyncio.gather(*tasks_to_wait)

        logger.info(APP_FINISHED_BANNER_MSG)
        loop.stop()

    def list_running(self) -> str:
        return "\n- ".join(["Running tasks:"] + list(self._registered_coroutines))

    def add_job(
        self,
        target: Callable,
        *args: Any,
        repeat_interval_s: Optional[PositiveFloat] = None
    ) -> None:
        async def _task_runner() -> None:
            while True:
                coroutine: Coroutine = target(*args)
                logger.info("Running '%s'", coroutine.__name__)
                try:
                    await coroutine
                except Exception as e:  # pylint: disable=broad-except

                    logger.error(
                        "Had an error while running '%s':\n%s",
                        coroutine.__name__,
                        "\n".join(traceback.format_tb(e.__traceback__)),
                    )

                if repeat_interval_s is None:
                    logger.warning(
                        "Unexpected termination of '%s'; it will be restarted",
                        coroutine.__name__,
                    )

                logger.info(
                    "Will run '%s' again in %s seconds",
                    coroutine.__name__,
                    repeat_interval_s,
                )
                await asyncio.sleep(
                    DEFAULT_TASK_WAIT_ON_ERROR
                    if repeat_interval_s is None
                    else repeat_interval_s
                )

        self._coroutines.add(_task_runner())
        self._registered_coroutines.add(target.__name__)

    def run(self) -> None:
        logger.info(APP_STARTED_BANNER_MSG)

        async def _get_tasks_from_coroutines() -> None:
            for coroutine in self._coroutines:
                self._tasks.add(asyncio.create_task(coroutine))

        self._loop.run_until_complete(_get_tasks_from_coroutines())
        self._loop.run_forever()
