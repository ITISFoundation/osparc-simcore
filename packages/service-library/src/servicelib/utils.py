""" General utils

IMPORTANT: lowest level module
   I order to avoid cyclic dependences, please
   DO NOT IMPORT ANYTHING from .
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Coroutine, Optional, Union

logger = logging.getLogger(__name__)


def is_production_environ() -> bool:
    """
    If True, this code most probably
    runs in a production container of one of the
    osparc-simcore services.
    """
    # WARNING: based on a convention that is not constantly verified
    return os.environ.get("SC_BUILD_TARGET") == "production"


def get_http_client_request_total_timeout() -> Optional[int]:
    return int(os.environ.get("HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT", "20")) or None


def get_http_client_request_aiohttp_connect_timeout() -> Optional[int]:
    return int(os.environ.get("HTTP_CLIENT_REQUEST_AIOHTTP_CONNECT_TIMEOUT", 0)) or None


def get_http_client_request_aiohttp_sock_connect_timeout() -> Optional[int]:
    return (
        int(os.environ.get("HTTP_CLIENT_REQUEST_AIOHTTP_SOCK_CONNECT_TIMEOUT", "5"))
        or None
    )


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
    obj: Coroutine,
    *,
    task_suffix_name: str,
    fire_and_forget_tasks_collection: set[asyncio.Task],
) -> asyncio.Task:
    task = asyncio.create_task(obj, name=f"fire_and_forget_task_{task_suffix_name}")
    fire_and_forget_tasks_collection.add(task)

    def log_exception_callback(fut: asyncio.Future):
        try:
            fut.result()
        except asyncio.CancelledError:
            logger.warning("%s spawned as fire&forget was cancelled", fut)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error occurred while running task %s!", task.get_name())

    task.add_done_callback(log_exception_callback)
    task.add_done_callback(fire_and_forget_tasks_collection.discard)
    return task


# // tasks
async def logged_gather(
    *tasks: Awaitable[Any],
    reraise: bool = True,
    log: logging.Logger = logger,
    max_concurrency: int = 0,
) -> list[Any]:
    """
        Thin wrapper around asyncio.gather that allows excuting ALL tasks concurently until the end
        even if any of them fail. Finally, all errors are logged and the first raised (if reraise=True)
        as asyncio.gather would do with return_exceptions=True

        WARNING: Notice that not stopping after the first exception is raised, adds the
        risk that some tasks might terminate with unhandled exceptions. To avoid this
        use directly asyncio.gather(*tasks, return_exceptions=True).

    :param reraise: reraises first exception (in order the tasks were passed) concurrent tasks, defaults to True
    :param log: passing the logger gives a chance to identify the origin of the gather call, defaults to current submodule's logger
    :return: list of tasks results and errors e.g. [1, 2, ValueError("task3 went wrong"), 33, "foo"]
    """

    wrapped_tasks = tasks
    if max_concurrency > 0:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def sem_task(task: Awaitable[Any]) -> Any:
            async with semaphore:
                return await task

        wrapped_tasks = [sem_task(t) for t in tasks]

    results = await asyncio.gather(*wrapped_tasks, return_exceptions=True)

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
