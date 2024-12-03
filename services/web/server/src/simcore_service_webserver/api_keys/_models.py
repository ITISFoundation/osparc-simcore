import datetime as dt
from dataclasses import dataclass


@dataclass
class ApiKey:
    id: str
    display_name: str
    expiration: dt.timedelta
    api_key: str
    api_secret: str
