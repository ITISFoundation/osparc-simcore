from datetime import datetime

import pytest
from servicelib.docker import to_datetime


@pytest.mark.parametrize(
    "docker_time, expected_datetime",
    [("2020-10-09T12:28:14.771034099Z", datetime(2020, 10, 9, 12, 28, 14, 771034))],
)
def test_to_datetime(docker_time: str, expected_datetime: datetime):
    assert to_datetime(docker_time) == expected_datetime
