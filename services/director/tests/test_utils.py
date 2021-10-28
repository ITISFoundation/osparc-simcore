from datetime import datetime

import pytest
from simcore_service_director.utils import parse_as_datetime


# Samples taken from https://docs.docker.com/engine/reference/commandline/service_inspect/
@pytest.mark.parametrize(
    "timestr",
    (
        "2020-10-09T18:44:02.558012087Z",
        "2020-10-09T12:28:14.771034099Z",
        "2020-10-09T12:28:14.7710",
        "2020-10-09T12:28:14.77 Z",
        "2020-10-09T12:28",
    ),
)
def test_parse_valid_time_strings(timestr):

    dt = parse_as_datetime(timestr)
    assert isinstance(dt, datetime)
    assert dt.year == 2020
    assert dt.month == 10
    assert dt.day == 9


def test_parse_invalid_timestr():
    now = datetime.utcnow()
    invalid_timestr = "asdfasdf"

    # w/ default, it should NOT raise
    dt = parse_as_datetime(invalid_timestr, default=now)
    assert dt == now

    # w/o default
    with pytest.raises(ValueError):
        parse_as_datetime(invalid_timestr)
