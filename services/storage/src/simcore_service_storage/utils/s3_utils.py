import asyncio
import datetime
import logging
from collections import defaultdict
from dataclasses import dataclass, field

from common_library.async_tools import cancel_and_wait
from pydantic import ByteSize, TypeAdapter
from servicelib.background_task import create_periodic_task
from servicelib.progress_bar import ProgressBarData

_logger = logging.getLogger(__name__)


@dataclass
class S3TransferDataCB:
    task_progress: ProgressBarData
    total_bytes_to_transfer: ByteSize
    task_progress_message_prefix: str = ""
    _total_bytes_copied: int = 0
    _file_total_bytes_copied: dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    _update_task_event: asyncio.Event = field(default_factory=asyncio.Event)
    _async_update_periodic_task: asyncio.Task | None = None

    def __post_init__(self) -> None:
        self._async_update_periodic_task = create_periodic_task(
            self._async_update,
            interval=datetime.timedelta(seconds=0.2),
            task_name="s3_transfer_cb_update",
        )
        self._update()

    async def __aenter__(self) -> "S3TransferDataCB":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        self.finalize_transfer()
        await asyncio.sleep(0)
        assert self._async_update_periodic_task  # nosec
        await cancel_and_wait(self._async_update_periodic_task)

    async def _async_update(self) -> None:
        await self._update_task_event.wait()
        self._update_task_event.clear()
        self.task_progress.description = (
            f"{self.task_progress_message_prefix} - "
            f"{self.total_bytes_to_transfer.human_readable()}"
        )
        await self.task_progress.set_(
            min(self._total_bytes_copied, self.total_bytes_to_transfer)
            / (self.total_bytes_to_transfer or 1)
        )

    def _update(self) -> None:
        self._update_task_event.set()

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
