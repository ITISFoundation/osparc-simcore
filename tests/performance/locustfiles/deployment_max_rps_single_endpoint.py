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
from common.auth_settings import DeploymentAuth, OsparcAuth
from locust import FastHttpUser, events, task

logging.basicConfig(level=logging.INFO)

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
    logging.info("Testing endpoint: %s", environment.parsed_options.endpoint)
    logging.info("Requires login: %s", environment.parsed_options.requires_login)


class WebApiUser(FastHttpUser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.deploy_auth = DeploymentAuth()
        logging.debug("Using deployment auth: %s", self.deploy_auth)

        if self.environment.parsed_options.requires_login:
            self.osparc_auth = OsparcAuth()
            logging.debug("Using OsparcAuth for login: %s", self.osparc_auth)

    @task
    def get_endpoint(self) -> None:
        self.client.get(
            self.environment.parsed_options.endpoint, auth=self.deploy_auth.to_auth()
        )

    def _login(self) -> None:
        # Implement login logic here
        logging.info(
            "Loggin in user with email: %s",
            {
                "email": self.osparc_auth.OSPARC_USER_NAME,
                "password": self.osparc_auth.OSPARC_PASSWORD.get_secret_value(),
            },
        )
        response = self.client.post(
            "/v0/auth/login",
            json={
                "email": self.osparc_auth.OSPARC_USER_NAME,
                "password": self.osparc_auth.OSPARC_PASSWORD.get_secret_value(),
            },
            auth=self.deploy_auth.to_auth(),
        )
        response.raise_for_status()
        logging.info("Logged in user with email: %s", self.osparc_auth)

    def _logout(self) -> None:
        # Implement logout logic here
        self.client.post("/v0/auth/logout", auth=self.deploy_auth.to_auth())
        logging.info("Logged out user with email: %s", self.osparc_auth)

    def on_start(self) -> None:
        if self.environment.parsed_options.requires_login:
            self._login()

    def on_stop(self) -> None:
        if self.environment.parsed_options.requires_login:
            self._logout()
