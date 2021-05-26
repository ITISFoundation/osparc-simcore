#
# SEE https://docs.locust.io/en/stable/quickstart.html
#

import logging

import locust_plugins
from dotenv import load_dotenv
from locust import task
from locust.contrib.fasthttp import FastHttpUser

logging.basicConfig(level=logging.INFO)


load_dotenv()  # take environment variables from .env


class WebApiUser(FastHttpUser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @task(10)
    def get_root(self):
        self.client.get(
            "",
        )

    @task(10)
    def get_root_slash(self):
        self.client.get(
            "/",
        )

    @task(1)
    def get_health(self):
        self.client.get(
            "/v0/health",
        )

    def on_start(self):
        print("Created locust user")

    def on_stop(self):
        print("Stopping locust user")
