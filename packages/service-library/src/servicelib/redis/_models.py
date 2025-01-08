import datetime
from dataclasses import dataclass

from settings_library.redis import RedisDatabase

from ._constants import DEFAULT_DECODE_RESPONSES, DEFAULT_HEALTH_CHECK_INTERVAL


@dataclass(frozen=True, kw_only=True)
class RedisManagerDBConfig:
    database: RedisDatabase
    decode_responses: bool = DEFAULT_DECODE_RESPONSES
    health_check_interval: datetime.timedelta = DEFAULT_HEALTH_CHECK_INTERVAL
