from datetime import timedelta

import pytest
from servicelib.utils_formatting import timedelta_as_minute_second


@pytest.mark.parametrize(
    "input_timedelta, expected_formatting",
    [
        (timedelta(), "00:00"),
        (timedelta(seconds=23), "00:23"),
        (timedelta(days=2, seconds=23), f"{2*24*60}:23"),
        (timedelta(seconds=-23), "-00:23"),
        (timedelta(seconds=-83), "-01:23"),
    ],
)
def test_timedelta_as_minute_second(
    input_timedelta: timedelta, expected_formatting: str
):
    assert timedelta_as_minute_second(input_timedelta) == expected_formatting
