import asyncio
import signal
from contextlib import suppress
from typing import Coroutine

from ._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG
from .settings import ApplicationSettings
from .volumes_cleanup import backup_and_remove_volumes


class Application:
    HANDLED_EXIT_SIGNALS: set[signal.Signals] = {signal.SIGTERM, signal.SIGINT}

    def __init__(self):
        self._loop = asyncio.get_event_loop()
        for sig_name in self.HANDLED_EXIT_SIGNALS:
            self._loop.add_signal_handler(
                sig_name,
                lambda: self._loop.create_task(self._exit_gracefully(self._loop)),
            )

        self._keep_running: bool = True

        self._tasks: set[asyncio.Task] = set()
        self._coroutines: set[Coroutine] = set()

    async def _exit_gracefully(self, loop: asyncio.AbstractEventLoop):
        for task in self._tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        print(APP_FINISHED_BANNER_MSG)
        loop.stop()

    def add_coroutine(self, coroutine: Coroutine) -> None:
        self._coroutines.add(coroutine)

    def run(self) -> None:
        print(APP_STARTED_BANNER_MSG)

        async def _get_tasks_from_coroutines() -> None:
            for coroutine in self._coroutines:
                self._tasks.add(asyncio.create_task(coroutine))

        self._loop.run_until_complete(_get_tasks_from_coroutines())
        self._loop.run_forever()


def create_application() -> Application:
    app = Application()

    settings = ApplicationSettings.create_from_envs()

    app.add_coroutine(backup_and_remove_volumes(settings))

    return app
