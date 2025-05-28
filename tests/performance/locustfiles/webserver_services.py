#
# SEE https://docs.locust.io/en/stable/quickstart.html
#

import json
import logging
import urllib
import urllib.parse
from typing import Any

import locust
from common.base_user import OsparcWebUserBase
from locust import events
from locust.env import Environment

_logger = logging.getLogger(__name__)


@events.init.add_listener
def _(environment: Environment, **_kwargs: Any) -> None:
    """
    Log the testing environment options when Locust initializes.

    Args:
        environment: The Locust environment
        _kwargs: Additional keyword arguments
    """
    # Log that this test requires login
    _logger.info(
        "This test requires login (requires_login=True class attribute is set)."
    )

    # Only log the parsed options, as the full environment is not JSON serializable
    assert (
        environment.parsed_options is not None
    ), "Environment parsed options must not be None"
    options_dict: dict[str, Any] = vars(environment.parsed_options)
    _logger.info("Testing environment options: %s", json.dumps(options_dict, indent=2))


class WebApiUser(OsparcWebUserBase):
    """Web API user that always requires login regardless of command line flags."""

    # This overrides the class attribute in OsparcWebUserBase
    requires_login = True

    @locust.task
    def list_latest_services(self):
        base_url = "/v0/catalog/services/-/latest"
        params = {"offset": 0, "limit": 20}
        page_num = 0
        while True:
            response = self.authenticated_get(
                base_url, params=params, name=f"{base_url}/{page_num}"
            )
            response.raise_for_status()

            page = response.json()

            # Process the current page data here
            next_link = page["data"]["_links"].get("next")
            if not next_link:
                break

            # Update base_url and params for the next request
            page_num += 1
            parsed_next = urllib.parse.urlparse(next_link)
            base_url = parsed_next.path
            params = dict(urllib.parse.parse_qsl(parsed_next.query))

            _logger.info(params)
