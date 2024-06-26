""" General utils

IMPORTANT: lowest level module
   I order to avoid cyclic dependences, please
   DO NOT IMPORT ANYTHING from .
"""

import asyncio
import logging
import os
import socket
from collections.abc import Awaitable, Coroutine, Generator, Iterable
from pathlib import Path
from typing import Any, AsyncGenerator, AsyncIterable, Final, TypeVar, cast

import toolz
from pydantic import NonNegativeInt

_logger = logging.getLogger(__name__)


def is_production_environ() -> bool:
    """
    If True, this code most probably
    runs in a production container of one of the
    osparc-simcore services.
    """
    # WARNING: based on a convention that is not constantly verified
    return os.environ.get("SC_BUILD_TARGET") == "production"


def get_http_client_request_total_timeout() -> int | None:
    return int(os.environ.get("HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT", "20")) or None


def get_http_client_request_aiohttp_connect_timeout() -> int | None:
    return int(os.environ.get("HTTP_CLIENT_REQUEST_AIOHTTP_CONNECT_TIMEOUT", 0)) or None


def get_http_client_request_aiohttp_sock_connect_timeout() -> int | None:
    return (
        int(os.environ.get("HTTP_CLIENT_REQUEST_AIOHTTP_SOCK_CONNECT_TIMEOUT", "5"))
        or None
    )


_EXPECTED: Final = {".github", "packages", "services"}


def is_osparc_repo_dir(path: Path) -> bool:
    dirnames = [p.name for p in path.iterdir() if p.is_dir()]
    return all(name in dirnames for name in _EXPECTED)


def search_osparc_repo_dir(start: str | Path, max_iterations=8) -> Path | None:
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
    # NOTE: details on rationale in https://github.com/ITISFoundation/osparc-simcore/pull/3120
    task = asyncio.create_task(obj, name=f"fire_and_forget_task_{task_suffix_name}")
    fire_and_forget_tasks_collection.add(task)

    def _log_exception_callback(fut: asyncio.Future):
        try:
            fut.result()
        except asyncio.CancelledError:
            _logger.warning("%s spawned as fire&forget was cancelled", fut)
        except Exception:  # pylint: disable=broad-except
            _logger.exception("Error occurred while running task %s!", task.get_name())

    task.add_done_callback(_log_exception_callback)
    task.add_done_callback(fire_and_forget_tasks_collection.discard)
    return task


# // tasks
async def logged_gather(
    *tasks: Awaitable[Any],
    reraise: bool = True,
    log: logging.Logger = _logger,
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
    wrapped_tasks: tuple | list
    if max_concurrency > 0:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def sem_task(task: Awaitable[Any]) -> Any:
            async with semaphore:
                return await task

        wrapped_tasks = [sem_task(t) for t in tasks]
    else:
        wrapped_tasks = tasks

    results: list[Any] = await asyncio.gather(*wrapped_tasks, return_exceptions=True)

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


def ensure_ends_with(input_string: str, char: str) -> str:
    if not input_string.endswith(char):
        input_string += char
    return input_string


def partition_gen(
    input_list: Iterable, *, slice_size: NonNegativeInt
) -> Generator[tuple[Any, ...], None, None]:
    """
    Given an iterable and the slice_size yields tuples containing
    slice_size elements in them.

    Inputs:
        input_list= [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
        slice_size = 5
    Outputs:
        [(1, 2, 3, 4, 5), (6, 7, 8, 9, 10), (11, 12, 13)]

    """
    if not input_list:
        yield ()

    yield from toolz.partition_all(slice_size, input_list)


def unused_port() -> int:
    """Return a port that is unused on the current host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return cast(int, s.getsockname()[1])


T = TypeVar("T")


async def limited_as_completed(
    awaitables: Iterable[Awaitable[T]] | AsyncIterable[Awaitable[T]], *, limit: int = 1
) -> AsyncGenerator[asyncio.Future[T], None]:
    """Runs awaitables using limited concurrent tasks and returns
    result futures unordered.

    Arguments:
        awaitables -- The awaitables to limit the concurrency of.

    Keyword Arguments:
        limit -- The maximum number of awaitables to run concurrently.
                0 or negative values disables the limit. (default: {1})

    Returns:
        nothing

    Yields:
        Future[T]: the future of the awaitables as they appear.


    """
    try:
        awaitable_iterator = aiter(awaitables)  # type: ignore[arg-type]
        is_async = True
    except TypeError:
        assert isinstance(awaitables, Iterable)  # nosec
        awaitable_iterator = iter(awaitables)  # type: ignore[assignment]
        is_async = False

    completed_all_awaitables = False
    pending_futures: set[asyncio.Future] = set()

    while pending_futures or not completed_all_awaitables:
        while (
            limit < 1 or len(pending_futures) < limit
        ) and not completed_all_awaitables:
            try:
                aw = (
                    await anext(awaitable_iterator)
                    if is_async
                    else next(awaitable_iterator)  # type: ignore[call-overload]
                )
                pending_futures.add(asyncio.ensure_future(aw))
            except (StopIteration, StopAsyncIteration):  # noqa: PERF203
                completed_all_awaitables = True
        if not pending_futures:
            return
        done, pending_futures = await asyncio.wait(
            pending_futures, return_when=asyncio.FIRST_COMPLETED
        )

        for future in done:
            yield future


async def _wrapped(
    awaitable: Awaitable[T], *, index: int, reraise: bool, logger: logging.Logger
) -> tuple[int, T | BaseException]:
    try:
        return index, await awaitable
    except BaseException as exc:  # pylint: disable=broad-exception-caught
        logger.warning(
            "Error in %i-th concurrent task %s: %s",
            index + 1,
            f"{awaitable=}",
            f"{exc=}",
        )
        if reraise:
            raise
        return index, exc


async def limited_gather(
    *awaitables: Awaitable[T],
    reraise: bool = True,
    log: logging.Logger = _logger,
    limit: int = 1,
) -> list[T | BaseException | None]:
    """runs all the awaitables using the limited concurrency and returns them in the same order

    Arguments:
        awaitables -- The awaitables to limit the concurrency of.

    Keyword Arguments:
        limit -- The maximum number of awaitables to run concurrently.
                setting 0 or negative values disable (default: {1})
        reraise -- if True will raise at the first exception
                The remaining tasks will continue as in standard asyncio gather.
                If False, then the exceptions will be returned (default: {True})

    Returns:
       the results of the awaitables keeping the order

       special thanks to: https://death.andgravity.com/limit-concurrency
    """

    indexed_awaitables = [
        _wrapped(awaitable, reraise=reraise, index=index, logger=log)
        for index, awaitable in enumerate(awaitables)
    ]

    results: list[T | BaseException | None] = [None] * len(indexed_awaitables)
    async for future in limited_as_completed(indexed_awaitables, limit=limit):
        index, result = await future
        results[index] = result

    return results
