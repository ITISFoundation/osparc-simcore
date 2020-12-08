""" General utils

IMPORTANT: lowest level module
   I order to avoid cyclic dependences, please
   DO NOT IMPORT ANYTHING from .
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Coroutine, List, Optional, Union

logger = logging.getLogger(__name__)


def is_production_environ() -> bool:
    """
    If True, this code most probably
    runs in a production container of one of the
    osparc-simcore services.
    """
    # WARNING: based on a convention that is not constantly verified
    return os.environ.get("SC_BUILD_TARGET") == "production"


def get_http_client_request_total_timeout() -> int:
    # search for the env variable containing the timeout or default is 20 if not set
    return int(os.environ.get("HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT", "20"))


def is_osparc_repo_dir(path: Path) -> bool:
    # TODO: implement with git cli
    expected = (".github", "packages", "services")
    got = [p.name for p in path.iterdir() if p.is_dir()]
    return all(d in got for d in expected)


def search_osparc_repo_dir(start: Union[str, Path], max_iterations=8) -> Optional[Path]:
    """Returns path to root repo dir or None if it does not exists

    NOTE: assumes starts is a path within repo
    """
    max_iterations = max(max_iterations, 1)
    root_dir = Path(start)
    iteration_number = 0
    while not is_osparc_repo_dir(root_dir) and iteration_number < max_iterations:
        root_dir = root_dir.parent
        iteration_number += 1

    return root_dir if is_osparc_repo_dir(root_dir) else None


# FUTURES
def fire_and_forget_task(
    obj: Union[Coroutine, asyncio.Future, Awaitable]
) -> asyncio.Future:
    future = asyncio.ensure_future(obj)

    def log_exception_callback(fut: asyncio.Future):
        try:
            fut.result()
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error occured while running task!")

    future.add_done_callback(log_exception_callback)
    return future


# // tasks
async def logged_gather(
    *tasks, reraise: bool = True, log: logging.Logger = logger
) -> List[Any]:
    """
        Thin wrapper around asyncio.gather that allows excuting ALL tasks concurently until the end
        even if any of them fail. Finally, all errors are logged and the first raised (if reraise=True)
        as asyncio.gather would do with return_exceptions=True

        WARNING: Notice that not stopping after the first exception is raised, adds the
        risk that some tasks might terminate with unhandled exceptions. To avoid this
        use directly asyncio.gather(*tasks, return_exceptions=True).

    :param reraise: reraises first exception (in order the tasks were passed) concurrent tasks, defaults to True
    :type reraise: bool, optional
    :param log: passing the logger gives a chance to identify the origin of the gather call, defaults to current submodule's logger
    :type log: logging.Logger, optional
    :return: list of tasks results and errors e.g. [1, 2, ValueError("task3 went wrong"), 33, "foo"]
    :rtype: List[Any]
    """
    results = await asyncio.gather(*tasks, return_exceptions=True)

    error = None
    for i, value in enumerate(results):
        if isinstance(value, Exception):
            log.warning(
                "Error in %i-th concurrent task %s: %s",
                i + 1,
                str(tasks[i]),
                str(value),
            )
            if not error:
                error = value

    if reraise and error:
        # WARNING: Notice that ONLY THE FIRST exception is raised.
        # The rest is all logged above.
        raise error

    return results
