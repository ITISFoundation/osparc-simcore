from datetime import datetime, timezone

import pytest
from servicelib.docker_utils import to_datetime

NOW = datetime.now(timezone.utc)


@pytest.mark.parametrize(
    "docker_time, expected_datetime",
    [
        (
            "2020-10-09T12:28:14.771034099Z",
            datetime(2020, 10, 9, 12, 28, 14, 771034),
        ),
        (NOW.strftime("%Y-%m-%dT%H:%M:%S.%f"), NOW),
    ],
)
def test_to_datetime(docker_time: str, expected_datetime: datetime):
    got_dt = to_datetime(docker_time)

    assert got_dt.replace(tzinfo=timezone.utc) == expected_datetime.replace(
        tzinfo=timezone.utc
    )


def test_to_datetime_conversion_known_errors():
    """
    Keeps an overview of formatting errors produced by 'to_datetime'
    """
    # this works
    to_datetime("2020-10-09T12:28:14.123456099Z")

    # When “Z” (Zulu) is tacked on the end of a time, it indicates that that time is UTC,
    # so really the literal Z is part of the time. What is T between date and time?
    # The T is just a literal to separate the date from the time,
    # and the Z means “zero hour offset” also known as “Zulu time” (UTC)
    with pytest.raises(ValueError) as err_info:
        # ValueError: unconverted data remains: Z
        # Z at the end (represnting ZULU = UTC) should be removed
        datetime.strptime("2020-10-09T12:28:14.123456Z", "%Y-%m-%dT%H:%M:%S.%f")

    assert err_info.value.args == ("unconverted data remains: Z",)

    # %f (milliseconds) has here 5 digits (can have at most 6) but to_datetime truncates after 6!
    # therefore it cannot understand Z
    with pytest.raises(ValueError) as err_info:
        # ValueError: unconverted data remains: Z
        to_datetime("2020-10-09T12:28:14.12345Z")

    assert err_info.value.args == ("unconverted data remains: Z",)

    # This was the error in pending_service_tasks_with_insufficient_resources
    # The 'T' is missing between the date and the time stamp
    with pytest.raises(ValueError) as err_info:
        # "time data '2023-03-15 13:01:21.774501' does not match format '%Y-%m-%dT%H:%M:%S.%f'"
        to_datetime(f"{datetime.now(timezone.utc)}")

    assert "time data" in err_info.value.args
    assert "does not match" in err_info.value.args
