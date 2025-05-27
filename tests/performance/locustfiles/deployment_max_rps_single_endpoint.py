#
# SEE https://docs.locust.io/en/stable/quickstart.html
#
# This script allows testing the maximum RPS against a single endpoint.
# Usage:
#   locust -f deployment_max_rps_single_endpoint.py --endpoint /v0/health
#
# If no endpoint is specified, the root endpoint ("/") will be used by default.
#

import logging

import locust_plugins
from common.base_user import OsparcWebUserBase
from locust import events, task

_logger = logging.getLogger(__name__)

# NOTE: 'import locust_plugins' is necessary to use --check-fail-ratio
# this assert is added to avoid that pycln pre-commit hook does not
# remove the import (the tool assumes the import is not necessary)
assert locust_plugins  # nosec


# Register the custom argument with Locust's parser
@events.init_command_line_parser.add_listener
def _(parser) -> None:
    parser.add_argument(
        "--endpoint",
        type=str,
        default="/",
        help="The endpoint to test (e.g., /v0/health)",
    )
    parser.add_argument(
        "--requires-login",
        action="store_true",
        default=False,
        help="Indicates if the user requires login before accessing the endpoint",
    )


@events.init.add_listener
def _(environment, **_kwargs) -> None:
    _logger.info("Testing endpoint: %s", environment.parsed_options.endpoint)
    _logger.info("Requires login: %s", environment.parsed_options.requires_login)


class WebApiUser(OsparcWebUserBase):
    @task
    def get_endpoint(self) -> None:
        self.authenticated_get(self.environment.parsed_options.endpoint)
