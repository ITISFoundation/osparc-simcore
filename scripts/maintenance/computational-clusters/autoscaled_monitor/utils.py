import asyncio
import datetime
import functools
from typing import Awaitable, Callable, ParamSpec, TypeVar

import arrow
from mypy_boto3_ec2.service_resource import Instance

from .constants import DANGER, HOUR


def timedelta_formatting(
    time_diff: datetime.timedelta, *, color_code: bool = False
) -> str:
    formatted_time_diff = f"{time_diff.days} day(s), " if time_diff.days > 0 else ""
    formatted_time_diff += f"{time_diff.seconds // 3600:02}:{(time_diff.seconds // 60) % 60:02}:{time_diff.seconds % 60:02}"
    if time_diff.days and color_code:
        formatted_time_diff = f"[red]{formatted_time_diff}[/red]"
    elif (time_diff.seconds > 5 * HOUR) and color_code:
        formatted_time_diff = f"[orange]{formatted_time_diff}[/orange]"
    return formatted_time_diff


def get_instance_name(instance: Instance) -> str:
    for tag in instance.tags:
        assert "Key" in tag  # nosec
        if tag["Key"] == "Name":
            return tag.get("Value", "unknown")
    return "unknown"


def get_last_heartbeat(instance: Instance) -> datetime.datetime | None:
    for tag in instance.tags:
        assert "Key" in tag  # nosec
        if tag["Key"] == "last_heartbeat":
            assert "Value" in tag  # nosec
            return arrow.get(tag["Value"]).datetime
    return None


def color_encode_with_state(string: str, ec2_instance: Instance) -> str:
    return (
        f"[green]{string}[/green]"
        if ec2_instance.state["Name"] == "running"
        else f"[yellow]{string}[/yellow]"
    )


def color_encode_with_threshold(string: str, value, threshold) -> str:
    return string if value > threshold else DANGER.format(string)


P = ParamSpec("P")
R = TypeVar("R")


def to_async(func: Callable[P, R]) -> Callable[P, Awaitable[R]]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Awaitable[R]:
        loop = asyncio.get_running_loop()
        partial_func = functools.partial(func, *args, **kwargs)
        return loop.run_in_executor(None, partial_func)

    return wrapper
