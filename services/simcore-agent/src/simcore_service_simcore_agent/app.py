import asyncio
import logging
import signal
import traceback
from contextlib import suppress
from typing import Any, Callable, Coroutine, Final, Optional

from pydantic import PositiveFloat, PositiveInt
from servicelib.logging_utils import config_all_loggers

from ._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG
from .settings import ApplicationSettings
from .volumes_cleanup import backup_and_remove_volumes

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

    async def _exit_gracefully(self, loop: asyncio.AbstractEventLoop):
        for task in self._tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        logger.info(APP_FINISHED_BANNER_MSG)
        loop.stop()

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

    def run(self) -> None:
        logger.info(APP_STARTED_BANNER_MSG)

        async def _get_tasks_from_coroutines() -> None:
            for coroutine in self._coroutines:
                self._tasks.add(asyncio.create_task(coroutine))

        self._loop.run_until_complete(_get_tasks_from_coroutines())
        self._loop.run_forever()


def setup_logger(settings: ApplicationSettings):
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/3148
    logging.basicConfig(level=settings.LOGLEVEL.value)  # NOSONAR
    logging.root.setLevel(settings.LOGLEVEL.value)
    config_all_loggers()


def create_application() -> Application:
    app = Application()

    settings = ApplicationSettings.create_from_envs()
    setup_logger(settings)

    app.add_job(
        backup_and_remove_volumes,
        settings,
        repeat_interval_s=settings.SIMCORE_AGENT_INTERVAL_VOLUMES_CLEANUP_S,
    )

    return app
