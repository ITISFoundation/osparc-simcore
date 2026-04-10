import datetime


def timedelta_as_minute_second_ms(delta: datetime.timedelta) -> str:
    total_seconds = delta.total_seconds()
    minutes, rem_seconds = divmod(abs(total_seconds), 60)
    seconds, milliseconds = divmod(rem_seconds, 1)
    result = ""

    if int(minutes) != 0:
        result += f"{int(minutes)}m "

    if int(seconds) != 0:
        result += f"{int(seconds)}s "

    if int(milliseconds * 1000) != 0:
        result += f"{int(milliseconds * 1000)}ms"
    if not result:
        result = "<1ms"

    sign = "-" if total_seconds < 0 else ""

    return f"{sign}{result.strip()}"
