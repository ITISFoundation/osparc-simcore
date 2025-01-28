import logging
from collections import defaultdict
from dataclasses import dataclass, field

from pydantic import ByteSize, TypeAdapter
from servicelib.aiohttp.long_running_tasks.server import (
    ProgressMessage,
    ProgressPercent,
    TaskProgress,
)

_logger = logging.getLogger(__name__)


def update_task_progress(
    task_progress: TaskProgress | None,
    message: ProgressMessage | None = None,
    progress: ProgressPercent | None = None,
) -> None:
    _logger.debug("%s [%s]", message or "", progress or "n/a")
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
            f"{self.total_bytes_to_transfer.human_readable()}",
            ProgressPercent(
                min(self._total_bytes_copied, self.total_bytes_to_transfer)
                / (self.total_bytes_to_transfer or 1)
            ),
        )

    def finalize_transfer(self) -> None:
        self._total_bytes_copied = (
            self.total_bytes_to_transfer - self._total_bytes_copied
        )
        self._update()

    def copy_transfer_cb(self, total_bytes_copied: int, *, file_name: str) -> None:
        _logger.debug(
            "Copied %s of %s",
            TypeAdapter(ByteSize).validate_python(total_bytes_copied).human_readable(),
            file_name,
        )
        self._file_total_bytes_copied[file_name] = total_bytes_copied
        self._total_bytes_copied = sum(self._file_total_bytes_copied.values())
        if self.total_bytes_to_transfer != 0:
            self._update()

    def upload_transfer_cb(self, bytes_transferred: int, *, file_name: str) -> None:
        _logger.debug(
            "Uploaded %s of %s",
            TypeAdapter(ByteSize).validate_python(bytes_transferred).human_readable(),
            file_name,
        )
        self._file_total_bytes_copied[file_name] += bytes_transferred
        self._total_bytes_copied = sum(self._file_total_bytes_copied.values())
        if self.total_bytes_to_transfer != 0:
            self._update()
