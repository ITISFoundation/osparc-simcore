import logging
import re
from abc import abstractmethod

from servicelib.progress_bar import ProgressBarData

_logger = logging.getLogger(__name__)


class BaseRCloneLogParser:
    @abstractmethod
    async def __call__(self, logs: str) -> None:
        ...


class SyncProgressLogParser(BaseRCloneLogParser):
    """
    log processor that only yields and progress updates detected in the logs.
    """

    def __init__(self, progress_bar: ProgressBarData) -> None:
        self._last_update_value = 0
        self.progress_bar = progress_bar

    async def __call__(self, logs: str) -> None:
        # Try to do it with https://github.com/r1chardj0n3s/parse
        if "Transferred" not in logs:
            return

        to_parse = logs.split("Transferred")[-1]
        match = re.search(r"(\d{1,3})%", to_parse)
        if not match:
            return

        # extracting percentage and only emitting if
        # value is bigger than the one previously emitted
        # avoids to send the same progress twice
        percentage = int(match.group(1))
        if percentage > self._last_update_value:
            progress_delta = percentage - self._last_update_value
            await self.progress_bar.update(progress_delta)
            self._last_update_value = percentage


class DebugLogParser(BaseRCloneLogParser):
    async def __call__(self, logs: str) -> None:
        _logger.debug("|>>>| %s |", logs)
