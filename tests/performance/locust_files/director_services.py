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
        self.user_id = "my_user_id"

    @task()
    def get_services(self):
        self.client.get(
            "v0/services?user_id=" + self.user_id,
            headers={
                "x-simcore-products-name": "osparc",
            },
        )

    def on_start(self):
        print("Created User ")

    def on_stop(self):
        print("Stopping")
