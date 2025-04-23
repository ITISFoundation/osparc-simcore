import time
import urllib.parse
from datetime import datetime

from simcore_service_webserver.utils import (
    DATETIME_FORMAT,
    compose_support_error_msg,
    now_str,
    to_datetime,
)
from yarl import URL


def test_yarl_new_url_generation():
    base_url_with_autoencode = URL("http://director:8001/v0", encoded=False)
    service_key = "simcore/services/dynamic/smash"
    service_version = "1.0.3"

    # NOTE: careful, first we need to encode the "/" in this file path.
    # For that we need safe="" option
    assert urllib.parse.quote("/") == "/"
    assert urllib.parse.quote("/", safe="") == "%2F"
    assert urllib.parse.quote("%2F", safe="") == "%252F"

    quoted_service_key = urllib.parse.quote(service_key, safe="")

    # Since 1.6.x composition using '/' creates URLs with auto-encoding enabled by default
    assert (
        str(
            base_url_with_autoencode / "services" / quoted_service_key / service_version
        )
        == "http://director:8001/v0/services/simcore%252Fservices%252Fdynamic%252Fsmash/1.0.3"
    )

    # Passing encoded=True parameter prevents URL auto-encoding, user is responsible about URL correctness
    url_without_autoencode = URL(
        f"http://director:8001/v0/services/{quoted_service_key}/1.0.3", encoded=True
    )

    assert (
        str(url_without_autoencode)
        == "http://director:8001/v0/services/simcore%2Fservices%2Fdynamic%2Fsmash/1.0.3"
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


def test_compose_support_error_msg():

    msg = compose_support_error_msg(
        "first sentence for Mr.X   \n  Second sentence.",
        error_code="OEC:139641204989600",
        support_email="support@email.com",
    )
    assert (
        msg == "First sentence for Mr.X. Second sentence."
        " For more information please forward this message to support@email.com (supportID=OEC:139641204989600)"
    )
