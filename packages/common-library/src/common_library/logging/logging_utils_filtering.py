"""
This codes originates from this article
    https://medium.com/swlh/add-log-decorators-to-your-python-project-84094f832181

SEE also https://github.com/Delgan/loguru for a future alternative
"""

import logging
from typing import TypeAlias

_logger = logging.getLogger(__name__)

LoggerName: TypeAlias = str
MessageSubstring: TypeAlias = str


class GeneralLogFilter(logging.Filter):
    def __init__(self, filtered_routes: list[str]) -> None:
        super().__init__()
        self.filtered_routes = filtered_routes

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()

        # Check if the filtered routes exists in the message
        return not any(
            filter_criteria in msg for filter_criteria in self.filtered_routes
        )
