import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Optional, Type

from ..dask_utils import create_dask_worker_logger

logger = create_dask_worker_logger(__name__)


def _log_error(_: Any, path: Any, excinfo: Any) -> None:
    logger.error(
        "Failed to remove %s [reason: %s]. Please check if there are permission issues.",
        path,
        excinfo,
    )


@dataclass
class TaskSharedVolumes:
    base_path: Path

    def __post_init__(self) -> None:
        for folder in ["inputs", "outputs", "logs"]:
            folder_path = self.base_path / folder
            if folder_path.exists():
                logger.warning(
                    "The path %s already exists. It will be wiped out now.", folder_path
                )
                shutil.rmtree(folder_path, onerror=_log_error)
            # NOTE: PC->SAN: if rmtree fails, there is a risk of rewriting i/os that can start from here
            # we should guarantee at this point that these folders exists and are empty
            folder_path.mkdir(parents=True, exist_ok=True)
            logger.debug(
                "created %s in %s [%s]",
                f"{folder=}",
                f"{self.base_path=}",
                f"{folder_path.exists()=}",
            )

    @property
    def inputs_folder(self) -> Path:
        return self.base_path / "inputs"

    @property
    def outputs_folder(self) -> Path:
        return self.base_path / "outputs"

    @property
    def logs_folder(self) -> Path:
        return self.base_path / "logs"

    def cleanup(self) -> None:
        shutil.rmtree(self.base_path, onerror=_log_error)

    async def __aenter__(self) -> "TaskSharedVolumes":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await asyncio.get_event_loop().run_in_executor(None, self.cleanup)
