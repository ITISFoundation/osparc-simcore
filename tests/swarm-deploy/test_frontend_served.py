# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import List

import pytest
import requests
import tenacity
from docker.models.services import Service
from pytest_simcore.helpers.constants import MINUTE
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL


@pytest.mark.parametrize(
    "test_url,expected_in_content",
    [
        ("http://127.0.0.1:9081/", "osparc/boot.js"),
        ("http://127.0.0.1:9081/s4l/index.html", "Sim4Life"),
        ("http://127.0.0.1:9081/tis/index.html", "TI Treatment Planning"),
    ],
)
def test_product_frontend_app_served(
    simcore_stack_deployed_services: List[Service],
    traefik_service: URL,
    test_url: str,
    expected_in_content: str,
    loop,
):
    # NOTE: it takes a bit of time until traefik sets up the correct proxy and
    # the webserver takes time to start
    # TODO: determine wait times with pre-calibration step
    @tenacity.retry(
        wait=wait_fixed(5),
        stop=stop_after_delay(1 * MINUTE),
    )
    def request_test_url():
        resp = requests.get(test_url)
        assert (
            resp.ok
        ), f"Failed request {resp.url} with {resp.status_code}: {resp.reason}"
        return resp

    resp = request_test_url()

    # TODO: serch osparc-simcore commit id e.g. 'osparc-simcore v817d82e'
    assert resp.ok
    assert "text/html" in resp.headers["Content-Type"]
    assert expected_in_content in resp.text, "Expected boot not found in response"
