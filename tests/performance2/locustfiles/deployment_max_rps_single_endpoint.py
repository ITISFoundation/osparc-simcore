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
from locust import events, task
from locust.contrib.fasthttp import FastHttpUser

from tests.performance2.common.auth_settings import DeploymentAuth, OsparcAuth

logging.basicConfig(level=logging.INFO)

# NOTE: 'import locust_plugins' is necessary to use --check-fail-ratio
# this assert is added to avoid that pycln pre-commit hook does not
# remove the import (the tool assumes the import is not necessary)
assert locust_plugins  # nosec

# Use a mutable object to store endpoint
_endpoint_holder = {"endpoint": "/"}


def add_endpoint_argument(parser) -> None:
    parser.add_argument(
        "--endpoint",
        type=str,
        default="/",
        help="The endpoint to test (e.g., /v0/health)",
    )


# Register the custom argument with Locust's parser
@events.init_command_line_parser.add_listener
def _(parser):
    add_endpoint_argument(parser)


@events.init.add_listener
def _(environment, **_kwargs) -> None:
    _endpoint_holder["endpoint"] = environment.parsed_options.endpoint
    logging.info("Testing endpoint: %s", _endpoint_holder["endpoint"])


class WebApiUser(FastHttpUser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth = DeploymentAuth().to_auth()
        self.endpoint = _endpoint_holder["endpoint"]
        self.osparc_auth = OsparcAuth()
        self.requires_login = False

    @task
    def get_endpoint(self) -> None:
        self.client.get(self.endpoint, auth=self.auth)

    def _login(self) -> None:
        # Implement login logic here
        logging.info("Logging in user with email: %s", self.osparc_auth)

    def _logout(self) -> None:
        # Implement logout logic here
        logging.info("Logging out user with email: %s", self.osparc_auth)

    def on_start(self) -> None:
        if self.requires_login:
            self._login()

    def on_stop(self) -> None:
        if self.requires_login:
            self._logout()
