import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field

from pydantic import ByteSize, parse_obj_as
from servicelib.progress_bar import ProgressBarData

logger = logging.getLogger(__name__)


@dataclass
class S3TransferDataCB:
    task_progress: ProgressBarData
    total_bytes_to_transfer: ByteSize
    task_progress_message_prefix: str = ""
    _total_bytes_copied: int = 0
    _file_total_bytes_copied: dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )

    def __post_init__(self) -> None:
        self._update()

    def _update(self) -> None:
        asyncio.get_event_loop().run_until_complete(
            self.task_progress.set_(self._total_bytes_copied)
        )

    def finalize_transfer(self) -> None:
        self._total_bytes_copied = (
            self.total_bytes_to_transfer - self._total_bytes_copied
        )
        self._update()

    def copy_transfer_cb(self, total_bytes_copied: int, *, file_name: str) -> None:
        logger.debug(
            "Copied %s of %s",
            parse_obj_as(ByteSize, total_bytes_copied).human_readable(),
            file_name,
        )
        self._file_total_bytes_copied[file_name] = total_bytes_copied
        self._total_bytes_copied = sum(self._file_total_bytes_copied.values())
        if self.total_bytes_to_transfer != 0:
            self._update()

    def upload_transfer_cb(self, bytes_transferred: int, *, file_name: str) -> None:
        self._file_total_bytes_copied[file_name] += bytes_transferred
        self._total_bytes_copied = sum(self._file_total_bytes_copied.values())
        if self.total_bytes_to_transfer != 0:
            self._update()
