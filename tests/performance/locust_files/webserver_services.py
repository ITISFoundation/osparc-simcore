#
# SEE https://docs.locust.io/en/stable/quickstart.html
#

import logging
import urllib
import urllib.parse

import faker
import locust
from dotenv import load_dotenv
from locust.contrib.fasthttp import FastHttpUser

logging.basicConfig(level=logging.INFO)

fake = faker.Faker()

load_dotenv()  # take environment variables from .env


class WebApiUser(FastHttpUser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.email = fake.email()

    @locust.task
    def list_latest_services(self):
        base_url = "/v0/catalog/services/-/latest"
        params = {"offset": 20, "limit": 20}

        while True:
            response = self.client.get(base_url, params=params)
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
        print("Created User ", self.email)
        password = "testtesttest"  # noqa: S105

        self.client.post(
            "/v0/auth/register",
            json={
                "email": self.email,
                "password": password,
                "confirm": password,
            },
        )
        self.client.post(
            "/v0/auth/login",
            json={
                "email": self.email,
                "password": password,
            },
        )

    def on_stop(self):
        self.client.post("/v0/auth/logout")
        print("Stopping", self.email)
