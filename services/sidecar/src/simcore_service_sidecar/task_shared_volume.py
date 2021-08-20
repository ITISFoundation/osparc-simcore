import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

import aiopg

from .config import SIDECAR_INPUT_FOLDER, SIDECAR_LOG_FOLDER, SIDECAR_OUTPUT_FOLDER

log = logging.getLogger(__name__)


@dataclass
class TaskSharedVolumes:
    input_folder: Path
    output_folder: Path
    log_folder: Path

    @classmethod
    def from_task(cls, task: aiopg.sa.result.RowProxy):
        return cls(
            SIDECAR_INPUT_FOLDER / f"{task.job_id}",
            SIDECAR_OUTPUT_FOLDER / f"{task.job_id}",
            SIDECAR_LOG_FOLDER / f"{task.job_id}",
        )

    def create(self) -> None:
        for folder in [
            self.input_folder,
            self.output_folder,
            self.log_folder,
        ]:
            if folder.exists():
                shutil.rmtree(str(folder))
            folder.mkdir(parents=True, exist_ok=True)

    def delete(self) -> None:
        for folder in [
            self.input_folder,
            self.output_folder,
            self.log_folder,
        ]:
            if folder.exists():

                def log_error(_, path, excinfo):
                    log.warning(
                        "Failed to remove %s [reason: %s]. Should consider pruning files in host later",
                        path,
                        excinfo,
                    )

                shutil.rmtree(str(folder), onerror=log_error)
