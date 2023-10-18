import datetime

_TIME_FORMAT = "{:02d}:{:02d}"  # format for minutes:seconds


def timedelta_as_minute_second(delta: datetime.timedelta) -> str:
    total_seconds = round(delta.total_seconds())
    minutes, seconds = divmod(abs(total_seconds), 60)
    sign = "-" if total_seconds < 0 else ""
    return f"{sign}{_TIME_FORMAT.format(minutes, seconds)}"
