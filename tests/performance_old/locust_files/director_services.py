#
# SEE https://docs.locust.io/en/stable/quickstart.html
#

import logging

from locust import task
from locust.contrib.fasthttp import FastHttpUser

logging.basicConfig(level=logging.INFO)


class WebApiUser(FastHttpUser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = "my_user_id"

    @task()
    def get_services(self):
        self.client.get(
            f"v0/services?user_id={self.user_id}",
            headers={
                "x-simcore-products-name": "osparc",
            },
        )

    def on_start(self):  # pylint: disable=no-self-use
        print("Created User ")

    def on_stop(self):  # pylint: disable=no-self-use
        print("Stopping")
