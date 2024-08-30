import logging
from collections import defaultdict
from dataclasses import dataclass, field

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
    _file_total_bytes_copied: dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )

    def __post_init__(self) -> None:
        self._update()

    def _update(self) -> None:
        update_task_progress(
            self.task_progress,
            f"{self.task_progress_message_prefix} - "
            f"{parse_obj_as(ByteSize,self._total_bytes_copied).human_readable()}"
            f"/{self.total_bytes_to_transfer.human_readable()}]",
            ProgressPercent(
                min(self._total_bytes_copied, self.total_bytes_to_transfer)
                / self.total_bytes_to_transfer
            ),
        )

    def finalize_transfer(self) -> None:
        self._total_bytes_copied = (
            self.total_bytes_to_transfer - self._total_bytes_copied
        )
        self._update()

    def copy_transfer_cb(self, file_total_bytes: int, file_name: str) -> None:
        logger.debug(
            "Copied %s of %s",
            parse_obj_as(ByteSize, file_total_bytes).human_readable(),
            file_name,
        )
        self._file_total_bytes_copied[file_name] = file_total_bytes
        self._total_bytes_copied = sum(self._file_total_bytes_copied.values())
        if self.total_bytes_to_transfer != 0:
            self._update()

    def upload_transfer_cb(self, file_increment_bytes: int, file_name: str) -> None:
        self._file_total_bytes_copied[file_name] += file_increment_bytes
        self._total_bytes_copied = sum(self._file_total_bytes_copied.values())
        if self.total_bytes_to_transfer != 0:
            self._update()
