import json
import logging
from typing import Any

import locust_plugins
from locust import FastHttpUser, events
from locust.argument_parser import LocustArgumentParser
from locust.env import Environment

from .auth_settings import DeploymentAuth, OsparcAuth

_logger = logging.getLogger(__name__)

# NOTE: 'import locust_plugins' is necessary to use --check-fail-ratio
# this assert is added to avoid that pycln pre-commit hook does not
# remove the import (the tool assumes the import is not necessary)
assert locust_plugins  # nosec


class OsparcUserBase(FastHttpUser):
    """
    Base class for Locust users that provides common functionality.
    This class can be extended by specific user classes to implement
    different behaviors or tasks.
    """

    abstract = True  # This class is abstract and won't be instantiated by Locust

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.deploy_auth = DeploymentAuth()
        _logger.debug(
            "Using deployment auth with username: %s", self.deploy_auth.SC_USER_NAME
        )

    def authenticated_get(self, url, **kwargs):
        """Make GET request with deployment auth"""
        kwargs.setdefault("auth", self.deploy_auth.to_auth())
        return self.client.get(url, **kwargs)

    def authenticated_post(self, url, **kwargs):
        """Make POST request with deployment auth"""
        kwargs.setdefault("auth", self.deploy_auth.to_auth())
        return self.client.post(url, **kwargs)

    def authenticated_put(self, url, **kwargs):
        """Make PUT request with deployment auth"""
        kwargs.setdefault("auth", self.deploy_auth.to_auth())
        return self.client.put(url, **kwargs)

    def authenticated_delete(self, url, **kwargs):
        """Make DELETE request with deployment auth"""
        kwargs.setdefault("auth", self.deploy_auth.to_auth())
        return self.client.delete(url, **kwargs)

    def authenticated_patch(self, url, **kwargs):
        """Make PATCH request with deployment auth"""
        kwargs.setdefault("auth", self.deploy_auth.to_auth())
        return self.client.patch(url, **kwargs)


@events.init_command_line_parser.add_listener
def _(parser: LocustArgumentParser) -> None:
    parser.add_argument(
        "--requires-login",
        action="store_true",
        default=False,
        help="Indicates if the user requires login before accessing the endpoint",
    )


@events.init.add_listener
def _(environment: Environment, **_kwargs: Any) -> None:
    # Only log the parsed options, as the full environment is not JSON serializable
    options_dict: dict[str, Any] = vars(environment.parsed_options)
    _logger.debug("Testing environment options: %s", json.dumps(options_dict, indent=2))


class OsparcWebUserBase(OsparcUserBase):
    """
    Base class for web users in Locust that provides common functionality.
    This class can be extended by specific web user classes to implement
    different behaviors or tasks.
    """

    abstract = True  # This class is abstract and won't be instantiated by Locust
    requires_login = False  # Default value, can be overridden by subclasses

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Determine if login is required once during initialization
        self._login_required = (
            getattr(self.__class__, "requires_login", False)
            or self.environment.parsed_options.requires_login
        )

        # Initialize auth if login is required
        if self._login_required:
            self.osparc_auth = OsparcAuth()
            _logger.info(
                "Using OsparcAuth for login with username: %s",
                self.osparc_auth.OSPARC_USER_NAME,
            )

    def on_start(self) -> None:
        """
        Called when a web user starts. Can be overridden by subclasses
        to implement custom startup behavior, such as logging in.
        """
        if self._login_required:
            self._login()

    def on_stop(self) -> None:
        """
        Called when a web user stops. Can be overridden by subclasses
        to implement custom shutdown behavior, such as logging out.
        """
        if self._login_required:
            self._logout()

    def _login(self) -> None:
        # Implement login logic here
        response = self.authenticated_post(
            "/v0/auth/login",
            json={
                "email": self.osparc_auth.OSPARC_USER_NAME,
                "password": self.osparc_auth.OSPARC_PASSWORD.get_secret_value(),
            },
        )
        response.raise_for_status()
        _logger.debug(
            "Logged in user with email: %s", self.osparc_auth.OSPARC_USER_NAME
        )

    def _logout(self) -> None:
        # Implement logout logic here
        self.authenticated_post("/v0/auth/logout")
        _logger.debug(
            "Logged out user with email: %s", self.osparc_auth.OSPARC_USER_NAME
        )
