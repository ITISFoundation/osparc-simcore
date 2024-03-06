# pylint: disable=protected-access
from datetime import datetime, timezone

import pytest
from servicelib.docker_utils import to_datetime

NOW = datetime.now(tz=timezone.utc)


@pytest.mark.parametrize(
    "docker_time, expected_datetime",
    [
        (
            "2023-03-21T00:00:00Z",
            datetime(2023, 3, 21, 0, 0, tzinfo=timezone.utc),
        ),
        (
            "2023-12-31T23:59:59Z",
            datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        ),
        (
            "2020-10-09T12:28:14.771034099Z",
            datetime(2020, 10, 9, 12, 28, 14, 771034, tzinfo=timezone.utc),
        ),
        (
            "2020-10-09T12:28:14.123456099Z",
            datetime(2020, 10, 9, 12, 28, 14, 123456, tzinfo=timezone.utc),
        ),
        (
            "2020-10-09T12:28:14.12345Z",
            datetime(2020, 10, 9, 12, 28, 14, 123450, tzinfo=timezone.utc),
        ),
        (
            "2023-03-15 13:01:21.774501",
            datetime(2023, 3, 15, 13, 1, 21, 774501, tzinfo=timezone.utc),
        ),
        (f"{NOW}", NOW),
        (NOW.strftime("%Y-%m-%dT%H:%M:%S.%f"), NOW),
    ],
)
def test_to_datetime(docker_time: str, expected_datetime: datetime):
    received_datetime = to_datetime(docker_time)
    assert received_datetime == expected_datetime
