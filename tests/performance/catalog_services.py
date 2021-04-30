#
# SEE https://docs.locust.io/en/stable/quickstart.html
#

import logging
import os

import faker
from dotenv import load_dotenv
from locust import HttpUser, constant, task

logging.basicConfig(level=logging.INFO)

fake = faker.Faker()

load_dotenv()  # take environment variables from .env


class WebApiUser(HttpUser):
    wait_time = constant(
        1
    )  #  simulated users wait between 1 and 2.5 seconds after each task (see below) is executed.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.email = fake.email()

    # @task
    # def health_check(self):
    #     self.client.get("/v0/health")

    @task(weight=5)
    def get_services(self):
        self.client.get(
            f"/v0/catalog/services",
        )

    def on_start(self):
        print("Created User ", self.email)
        self.client.post(
            "/v0/auth/register",
            json={
                "email": self.email,
                "password": "my secret",
                "confirm": "my secret",
            },
        )
        self.client.post(
            "/v0/auth/login", json={"email": self.email, "password": "my secret"}
        )

    def on_stop(self):
        self.client.post("/v0/auth/logout")
        print("Stopping", self.email)
