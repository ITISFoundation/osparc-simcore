import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
_MAXLEN = len("2020-10-09T12:28:14.7710")


def parse_as_datetime(timestr: str, *, default: Optional[datetime] = None) -> datetime:
    """
    default: if parsing is not possible, it returs default

    """
    # datetime_str is typically '2020-10-09T12:28:14.771034099Z'
    #  - The T separates the date portion from the time-of-day portion
    #  - The Z on the end means UTC, that is, an offset-from-UTC
    # The 099 before the Z is not clear, therefore we will truncate the last part

    try:
        timestr = timestr.strip("Z ")[:_MAXLEN]
        dt = datetime.strptime(timestr, DATETIME_FORMAT)
        return dt
    except ValueError as err:
        log.debug("Failed to parse %s: %s", timestr, err)
        if default is not None:
            return default
        raise
