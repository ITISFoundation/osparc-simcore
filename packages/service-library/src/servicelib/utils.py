""" General utils

IMPORTANT: lowest level module
   I order to avoid cyclic dependences, please
   DO NOT IMPORT ANYTHING from .
"""
import asyncio
import logging
from pathlib import Path
from typing import Any, Coroutine, List, Optional, Union

logger = logging.getLogger(__name__)


def is_osparc_repo_dir(path: Path) -> bool:
    # TODO: implement with git cli
    expected = (".github", "packages", "services")
    got = [p.name for p in path.iterdir() if p.is_dir()]
    return all(d in got for d in expected)


def search_osparc_repo_dir(start: Union[str, Path], max_iterations=8) -> Optional[Path]:
    """ Returns path to root repo dir or None if it does not exists

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
def fire_and_forget_task(obj: Union[Coroutine, asyncio.Future]) -> None:
    future = asyncio.ensure_future(obj)

    def log_exception_callback(fut: asyncio.Future):
        try:
            fut.result()
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error occured while running task!")

    future.add_done_callback(log_exception_callback)


# // tasks
async def logged_gather(*tasks, reraise: bool = True) -> List[Any]:
    # all coroutine called in // and we take care of returning the exceptions
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for value in results:
        if isinstance(value, Exception):
            if reraise:
                raise value
            logger.error(
                "Exception occured while running %s: %s",
                str(tasks[results.index(value)]),
                str(value),
            )
    return results
