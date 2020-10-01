import time
from datetime import datetime

import pytest
from simcore_service_webserver.utils import (
    DATETIME_FORMAT,
    now_str,
    snake_to_camel,
    to_datetime,
)


def test_time_utils():
    snapshot0 = now_str()

    time.sleep(0.5)
    snapshot1 = now_str()

    now0 = to_datetime(snapshot0)
    now1 = to_datetime(snapshot1)
    assert now0 < now1

    # tests biyective
    now_time = datetime.utcnow()
    snapshot = now_time.strftime(DATETIME_FORMAT)
    assert now_time == datetime.strptime(snapshot, DATETIME_FORMAT)


@pytest.mark.parametrize(
    "subject,expected",
    [
        ("snAke_Fun", "snakeFun"),
        ("", ""),
        ("camelAlready", "camelAlready"),
        ("AlmostCamel", "almostcamel"),
        ("_S", "_s")
    ],
)
def test_snake_to_camel(subject, expected):
    assert snake_to_camel(subject) == expected
