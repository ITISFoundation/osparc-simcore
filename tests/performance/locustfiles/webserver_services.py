#
# SEE https://docs.locust.io/en/stable/quickstart.html
#

import logging
import urllib
import urllib.parse

import faker
import locust
from common.base_user import OsparcWebUserBase
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

fake = faker.Faker()

load_dotenv()  # take environment variables from .env


class WebApiUser(OsparcWebUserBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.email = fake.email()
        self.password = "testtesttest"  # noqa: S105

    @locust.task
    def list_latest_services(self):
        base_url = "/v0/catalog/services/-/latest"
        params = {"offset": 20, "limit": 20}

        while True:
            response = self.authenticated_get(base_url, params=params)
            response.raise_for_status()

            page = response.json()

            # Process the current page data here
            next_link = page["_links"].get("next")
            if not next_link:
                break

            # Update base_url and params for the next request
            parsed_next = urllib.parse.urlparse(next_link)
            base_url = parsed_next.path
            params = dict(urllib.parse.parse_qsl(parsed_next.query))

    def on_start(self):
        logging.info("Creating user with email: %s", self.email)

        # Register user
        self.authenticated_post(
            "/v0/auth/register",
            json={
                "email": self.email,
                "password": self.password,
                "confirm": self.password,
            },
        )

        # Login using the custom user credentials instead of the default ones
        logging.info("Logging in user with email: %s", self.email)
        response = self.authenticated_post(
            "/v0/auth/login",
            json={
                "email": self.email,
                "password": self.password,
            },
        )
        response.raise_for_status()
        logging.info("Logged in user with email: %s", self.email)

    def on_stop(self):
        # Logout
        self.authenticated_post("/v0/auth/logout")
        logging.info("Logged out user with email: %s", self.email)
