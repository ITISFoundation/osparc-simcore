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
from common.deploy_auth import MonitoringBasicAuth
from locust import events, task
from locust.contrib.fasthttp import FastHttpUser

logging.basicConfig(level=logging.INFO)

# NOTE: 'import locust_plugins' is necessary to use --check-fail-ratio
# this assert is added to avoid that pycln pre-commit hook does not
# remove the import (the tool assumes the import is not necessary)
assert locust_plugins  # nosec

# Use a mutable object to store endpoint
_endpoint_holder = {"endpoint": "/"}


def add_endpoint_argument(parser):
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
def _(environment, **_kwargs):
    _endpoint_holder["endpoint"] = environment.parsed_options.endpoint
    logging.info("Testing endpoint: %s", _endpoint_holder["endpoint"])


class WebApiUser(FastHttpUser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth = MonitoringBasicAuth().to_auth()
        self.endpoint = _endpoint_holder["endpoint"]

    @task
    def get_endpoint(self):
        self.client.get(self.endpoint, auth=self.auth)
