import datetime as dt
from dataclasses import dataclass


@dataclass
class ApiKey:
    id: str
    display_name: str
    expiration: dt.timedelta | None = None
    api_key: str | None = None
    api_secret: str | None = None
