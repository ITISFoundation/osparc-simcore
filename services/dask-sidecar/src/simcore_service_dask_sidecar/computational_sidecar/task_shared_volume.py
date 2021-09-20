import shutil
from dataclasses import dataclass
from pathlib import Path

from ..utils import create_dask_worker_logger

logger = create_dask_worker_logger(__name__)


@dataclass
class TaskSharedVolumes:
    input_folder: Path
    output_folder: Path
    log_folder: Path

    def create(self) -> None:
        logger.debug(
            "creating shared volume in %s",
            [self.input_folder, self.output_folder, self.log_folder],
        )
        for folder in [
            self.input_folder,
            self.output_folder,
            self.log_folder,
        ]:
            if folder.exists():
                shutil.rmtree(folder)
            folder.mkdir(parents=True, exist_ok=True)
