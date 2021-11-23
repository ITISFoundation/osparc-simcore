from pathlib import Path
from .pools import async_on_threadpool
import logging


logger = logging.getLogger()


def _rm_path_contents(path: Path) -> None:
    """recursively remove all files in directory"""
    if not path.is_dir():
        path.unlink()
        return

    for child in path.glob("*"):
        if child.is_file():
            logger.info("Removing file %s", child)
            child.unlink()
        else:

            _rm_path_contents(child)
    path.rmdir()
    logger.info("Removing directory %s", path)


async def remove_directory(path: Path, only_children: bool = False) -> None:
    """Optional parameter allows to remove all children and keep directory"""
    if not path.exists():
        return

    for child in path.glob("*"):
        await async_on_threadpool(
            # pylint: disable=cell-var-from-loop
            lambda: _rm_path_contents(child)
        )

    if not only_children:
        await async_on_threadpool(lambda: _rm_path_contents(path))
