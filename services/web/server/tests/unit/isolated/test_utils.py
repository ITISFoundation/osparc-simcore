import time
import urllib.parse
from datetime import datetime
from urllib.parse import unquote_plus

import pytest
import yarl
from simcore_service_webserver.utils import (
    DATETIME_FORMAT,
    now_str,
    snake_to_camel,
    to_datetime,
)
from yarl import URL


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
        # since it assumes snake, notice how these cases get flatten
        ("camelAlready", "camelalready"),
        ("AlmostCamel", "almostcamel"),
        ("_S", "S"),
    ],
)
def test_snake_to_camel(subject, expected):
    assert snake_to_camel(subject) == expected


def test_yarl_url_compose_changed_with_latest_release():
    # TODO: add tests and do this upgrade carefuly. Part of https://github.com/ITISFoundation/osparc-simcore/issues/2008
    #
    # With yarl=1.6.* failed tests/unit/isolated/test_director_api.py::test_director_workflow
    #
    # Actually is more consistent since
    #   services/simcore%2Fservices%2Fdynamic%2Fsmash/1.0.3  is decoposed as  [services, simcore%2Fservices%2Fdynamic%2Fsmash, 1.0.3]
    #
    api_endpoint = URL("http://director:8001/v0")
    service_key = "simcore/services/dynamic/smash"
    service_version = "1.0.3"

    url = (
        api_endpoint
        / "services"
        / urllib.parse.quote(service_key, safe="")
        / service_version
    )

    assert (
        "/",
        "v0",
        "services",
        service_key,
        service_version,
    ) == url.parts, f"In yarl==1.5.1, this fails in {yarl.__version__}"

    assert "simcore/services/dynamic/smash/1.0.3" == unquote_plus(
        "simcore%2Fservices%2Fdynamic%2Fsmash/1.0.3"
    )
    assert (
        urllib.parse.quote(service_key, safe="")
        == "simcore%2Fservices%2Fdynamic%2Fsmash"
    )
    assert (
        urllib.parse.quote_plus(service_key) == "simcore%2Fservices%2Fdynamic%2Fsmash"
    )
