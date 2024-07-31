import logging
import re

from pydantic import ByteSize, parse_obj_as
from servicelib.logging_utils import log_catch
from servicelib.progress_bar import ProgressBarData

from ._common_utils import BaseLogParser

_logger = logging.getLogger(__name__)


def _parse_size(log_string):
    match = re.search(r"^\w+ (?P<size>[^\/]+)", log_string)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        return value, unit
    return None, None


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
            value, unit = _parse_size(logs)
            if value and unit:
                _bytes = parse_obj_as(ByteSize, f"{value}{unit}")
                await self.progress_bar.set_(_bytes)
