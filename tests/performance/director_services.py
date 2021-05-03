#
# SEE https://docs.locust.io/en/stable/quickstart.html
#

import logging

from dotenv import load_dotenv
from locust import task
from locust.contrib.fasthttp import FastHttpUser

logging.basicConfig(level=logging.INFO)


load_dotenv()  # take environment variables from .env


class WebApiUser(FastHttpUser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @task()
    def get_services(self):
        self.client.get(
            f"/v0/services",
        )

    def on_start(self):
        print("Created User ")

    def on_stop(self):
        print("Stopping")
