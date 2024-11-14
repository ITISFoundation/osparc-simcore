import datetime
import logging
from typing import Union

from models_library.utils.change_case import snake_to_camel
from pydantic import BaseModel, ByteSize, ConfigDict, Field, TypeAdapter
from servicelib.logging_utils import log_catch
from servicelib.progress_bar import ProgressBarData

from ._utils import BaseLogParser

_logger = logging.getLogger(__name__)


class _RCloneSyncMessageBase(BaseModel):
    level: str = Field(..., description="log level")
    msg: str
    source: str = Field(..., description="source code information")
    time: datetime.datetime


class _RCloneSyncUpdatedMessage(_RCloneSyncMessageBase):
    object: str = Field(..., description="object file name")


class _RCloneSyncTransferCompletedMessage(_RCloneSyncMessageBase):
    object: str = Field(..., description="object file name")
    size: ByteSize


class _RCloneSyncTransferringStats(BaseModel):
    bytes: ByteSize
    total_bytes: ByteSize
    model_config = ConfigDict(alias_generator=snake_to_camel)


class _RCloneSyncTransferringMessage(_RCloneSyncMessageBase):
    stats: _RCloneSyncTransferringStats


_RCloneSyncMessages = Union[  # noqa: UP007
    _RCloneSyncTransferCompletedMessage,
    _RCloneSyncUpdatedMessage,
    _RCloneSyncTransferringMessage,
    _RCloneSyncMessageBase,
]


class SyncProgressLogParser(BaseLogParser):
    """
    log processor that only yields and progress updates detected in the logs.


    This command:
    rclone --use-mmap --buffer-size 0M --transfers 5 sync mys3:simcore/5cfdef88-013b-11ef-910e-0242ac14003e/2d544003-9eb8-47e4-bcf7-95a8c31845f7/workspace ./tests3 --progress
    generates this but the rclone modifies the terminal printed lines which python does not like so much
    Transferred:        4.666 GiB / 4.666 GiB, 100%, 530.870 MiB/s, ETA 0s
    Transferred:            4 / 4, 100%
    Elapsed time:         9.6s

    This other command:
    rclone --use-mmap --buffer-size 0M --transfers 5 --use-json-log --stats-log-level INFO -v --stats 500ms sync mys3:simcore/5cfdef88-013b-11ef-910e-0242ac14003e/2d544003-9eb8-47e4-bcf7-95a8c31845f7/workspace ./tests3
    prints stuff such as:
    {"level":"info","msg":"Copied (new)","object":"README.ipynb","objectType":"*s3.Object","size":5123,"source":"operations/copy.go:360","time":"2024-04-23T14:05:10.408277+00:00"}
    {"level":"info","msg":"Copied (new)","object":".hidden_do_not_remove","objectType":"*s3.Object","size":219,"source":"operations/copy.go:360","time":"2024-04-23T14:05:10.408246+00:00"}
    {"level":"info","msg":"Copied (new)","object":"10MBfile","objectType":"*s3.Object","size":10000000,"source":"operations/copy.go:360","time":"2024-04-23T14:05:10.437499+00:00"}
    {"level":"info","msg":"\nTransferred:   \t  788.167 MiB / 4.666 GiB, 16%, 0 B/s, ETA -\nTransferred:            3 / 4, 75%\nElapsed time:         0.5s\nTransferring:\n *                                       5GBfile: 16% /4.657Gi, 0/s, -\n\n","source":"accounting/stats.go:526","stats":{"bytes":826452830,"checks":0,"deletedDirs":0,"deletes":0,"elapsedTime":0.512036999,"errors":0,"eta":null,"fatalError":false,"renames":0,"retryError":false,"serverSideCopies":0,"serverSideCopyBytes":0,"serverSideMoveBytes":0,"serverSideMoves":0,"speed":0,"totalBytes":5010005342,"totalChecks":0,"totalTransfers":4,"transferTime":0.497064856,"transferring":[{"bytes":816447488,"dstFs":"/devel/tests3","eta":null,"group":"global_stats","name":"5GBfile","percentage":16,"size":5000000000,"speed":1662518962.4875596,"speedAvg":0,"srcFs":"mys3:simcore/5cfdef88-013b-11ef-910e-0242ac14003e/2d544003-9eb8-47e4-bcf7-95a8c31845f7/workspace"}],"transfers":3},"time":"2024-04-23T14:05:10.901275+00:00"}
    {"level":"info","msg":"\nTransferred:   \t    1.498 GiB / 4.666 GiB, 32%, 0 B/s, ETA -\nTransferred:            3 / 4, 75%\nElapsed time:         1.0s\nTransferring:\n *                                       5GBfile: 31% /4.657Gi, 0/s, -\n\n","source":"accounting/stats.go:526","stats":{"bytes":1608690526,"checks":0,"deletedDirs":0,"deletes":0,"elapsedTime":1.012386594,"errors":0,"eta":null,"fatalError":false,"renames":0,"retryError":false,"serverSideCopies":0,"serverSideCopyBytes":0,"serverSideMoveBytes":0,"serverSideMoves":0,"speed":0,"totalBytes":5010005342,"totalChecks":0,"totalTransfers":4,"transferTime":0.997407347,"transferring":[{"bytes":1598816256,"dstFs":"/devel/tests3","eta":null,"group":"global_stats","name":"5GBfile","percentage":31,"size":5000000000,"speed":1612559346.2428129,"speedAvg":0,"srcFs":"mys3:simcore/5cfdef88-013b-11ef-910e-0242ac14003e/2d544003-9eb8-47e4-bcf7-95a8c31845f7/workspace"}],"transfers":3},"time":"2024-04-23T14:05:11.40166+00:00"}
    But this prints each file, do we really want to keep bookkeeping of all this??? that can potentially be a lot of files

    """

    def __init__(self, progress_bar: ProgressBarData) -> None:
        self.progress_bar = progress_bar

    async def __call__(self, logs: str) -> None:
        _logger.debug("received logs: %s", logs)
        with log_catch(_logger, reraise=False):
            rclone_message: _RCloneSyncMessages = TypeAdapter(
                _RCloneSyncMessages
            ).validate_json(logs)

            if isinstance(rclone_message, _RCloneSyncTransferringMessage):
                await self.progress_bar.set_(rclone_message.stats.bytes)


class DebugLogParser(BaseLogParser):
    async def __call__(self, logs: str) -> None:
        _logger.debug("|>>>| %s |", logs)


class CommandResultCaptureParser(BaseLogParser):
    def __init__(self) -> None:
        super().__init__()
        self._logs: list[str] = []

    async def __call__(self, logs: str) -> None:
        self._logs.append(logs)

    def get_output(self) -> str:
        return "".join(self._logs)
