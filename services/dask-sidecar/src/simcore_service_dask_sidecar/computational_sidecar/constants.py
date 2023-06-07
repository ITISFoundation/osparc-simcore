import re
from typing import Final

LEGACY_SERVICE_LOG_FILE_NAME: Final[str] = "log.dat"
PARSE_LOG_INTERVAL_S: Final[float] = 0.5

DOCKER_LOG_REGEXP_WITH_TIMESTAMP: re.Pattern[str] = re.compile(
    r"^(?P<timestamp>(?:(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2}(?:\.\d+)?))(Z|[\+-]\d{2}:\d{2})?)"
    r"\s(?P<log>.*)$"
)
PROGRESS_REGEXP: re.Pattern[str] = re.compile(
    r"^(?:\[?progress\]?:?)?\s*"
    r"(?P<value>[0-1]?\.\d+|"
    r"\d+\s*(?:(?P<percent_sign>%)|"
    r"\d+\s*"
    r"(?P<percent_explicit>percent))|"
    r"\[?(?P<fraction>\d+\/\d+)\]?"
    r"|0|1)"
)
