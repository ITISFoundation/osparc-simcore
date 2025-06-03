import asyncio
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskSharedVolumes:
    base_path: Path

    def __post_init__(self) -> None:
        for folder in ["inputs", "outputs", "logs"]:
            folder_path = self.base_path / folder
            if folder_path.exists():
                logger.warning(
                    "The path %s already exists. It will be wiped out now.", folder_path
                )
                self.cleanup()

            assert not folder_path.exists()  # nosec
            folder_path.mkdir(parents=True)
            logger.info(
                "created %s in %s",
                f"{folder=}",
                f"{self.base_path=}",
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
        try:
            shutil.rmtree(self.base_path)
        except OSError:
            logger.exception(
                "Unexpected failure removing '%s'."
                "TIP: Please check if there are permission issues.",
                self.base_path,
            )
            raise

    async def __aenter__(self) -> "TaskSharedVolumes":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await asyncio.get_event_loop().run_in_executor(None, self.cleanup)
