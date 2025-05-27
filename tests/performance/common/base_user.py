import logging

from locust import FastHttpUser

from .auth_settings import DeploymentAuth, OsparcAuth

_logger = logging.getLogger(__name__)


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


class OsparcWebUserBase(OsparcUserBase):
    """
    Base class for web users in Locust that provides common functionality.
    This class can be extended by specific web user classes to implement
    different behaviors or tasks.
    """

    abstract = True  # This class is abstract and won't be instantiated by Locust

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.environment.parsed_options.requires_login:
            self.osparc_auth = OsparcAuth()
            _logger.debug(
                "Using OsparcAuth for login with username: %s",
                self.osparc_auth.OSPARC_USER_NAME,
            )

    def on_start(self) -> None:
        """
        Called when a web user starts. Can be overridden by subclasses
        to implement custom startup behavior, such as logging in.
        """
        if self.environment.parsed_options.requires_login:
            self._login()

    def on_stop(self) -> None:
        """
        Called when a web user stops. Can be overridden by subclasses
        to implement custom shutdown behavior, such as logging out.
        """
        if self.environment.parsed_options.requires_login:
            self._logout()

    def _login(self) -> None:
        # Implement login logic here
        logging.info(
            "Logging in user with email: %s",
            self.osparc_auth.OSPARC_USER_NAME,
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
        logging.info("Logged in user with email: %s", self.osparc_auth.OSPARC_USER_NAME)

    def _logout(self) -> None:
        # Implement logout logic here
        self.client.post("/v0/auth/logout", auth=self.deploy_auth.to_auth())
        logging.info(
            "Logged out user with email: %s", self.osparc_auth.OSPARC_USER_NAME
        )
