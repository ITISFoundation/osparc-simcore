import logging
from dataclasses import dataclass

from pydantic import ByteSize, parse_obj_as
from servicelib.aiohttp.long_running_tasks.server import (
    ProgressMessage,
    ProgressPercent,
    TaskProgress,
)

logger = logging.getLogger(__name__)


def update_task_progress(
    task_progress: TaskProgress | None,
    message: ProgressMessage | None = None,
    progress: ProgressPercent | None = None,
) -> None:
    logger.debug("%s [%s]", message or "", progress or "n/a")
    if task_progress:
        task_progress.update(message=message, percent=progress)


@dataclass
class S3TransferDataCB:
    task_progress: TaskProgress | None
    total_bytes_to_transfer: ByteSize
    task_progress_message_prefix: str = ""
    _total_bytes_copied: int = 0

    def __post_init__(self):
        self.copy_transfer_cb(0)

    def finalize_transfer(self):
        self.copy_transfer_cb(self.total_bytes_to_transfer - self._total_bytes_copied)

    def copy_transfer_cb(self, copied_bytes: int):
        self._total_bytes_copied += copied_bytes
        if self.total_bytes_to_transfer != 0:
            update_task_progress(
                self.task_progress,
                f"{self.task_progress_message_prefix} - "
                f"{parse_obj_as(ByteSize,self._total_bytes_copied).human_readable()}"
                f"/{self.total_bytes_to_transfer.human_readable()}]",
                self._total_bytes_copied / self.total_bytes_to_transfer,
            )
