import logging
import re

from pydantic import ByteSize, TypeAdapter
from servicelib.logging_utils import log_catch
from servicelib.progress_bar import ProgressBarData

from ._utils import BaseLogParser

_logger = logging.getLogger(__name__)


def _parse_size(log_string):
    match = re.search(r"^\w+ (?P<size>[^\/]+)", log_string)
    if match:
        return match.group("size")
    return None


class SyncAwsCliS3ProgressLogParser(BaseLogParser):
    """
    log processor that onlyyields progress updates detected in the logs.


    This command:
    aws --endpoint-url ENDPOINT_URL s3 sync s3://BUCKET/S3_KEY . --delete --no-follow-symlinks
    generates this log lines:
    Completed 2.9 GiB/4.9 GiB (102.8 MiB/s) with 1 file(s) remaining
    """

    def __init__(self, progress_bar: ProgressBarData) -> None:
        self.progress_bar = progress_bar

    async def __call__(self, logs: str) -> None:
        _logger.debug("received logs: %s", logs)
        with log_catch(_logger, reraise=False):
            if _size := _parse_size(logs):
                _bytes = TypeAdapter(ByteSize).validate_python(_size)
                await self.progress_bar.set_(_bytes)
