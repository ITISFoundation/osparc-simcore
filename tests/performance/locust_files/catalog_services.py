#
# SEE https://docs.locust.io/en/stable/quickstart.html
#

import logging
from time import time

import faker
from locust import task
from locust.contrib.fasthttp import FastHttpUser

logging.basicConfig(level=logging.INFO)

fake = faker.Faker()


class WebApiUser(FastHttpUser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.email = fake.email()

    @task()
    def get_services_with_details(self):
        start = time()
        with self.client.get(
            "/v0/services?user_id=1&details=true",
            headers={
                "x-simcore-products-name": "osparc",
            },
            catch_response=True,
        ) as response:
            response.raise_for_status()
            num_services = len(response.json())
            print(f"got {num_services} WITH DETAILS in {time() - start}s")
            response.success()

    @task()
    def get_services_without_details(self):
        start = time()
        with self.client.get(
            "/v0/services?user_id=1&details=false",
            headers={
                "x-simcore-products-name": "osparc",
            },
            catch_response=True,
        ) as response:
            response.raise_for_status()
            num_services = len(response.json())
            print(f"got {num_services} in {time() - start}s")
            response.success()

    def on_start(self):
        print("Created User ", self.email)

    def on_stop(self):
        print("Stopping", self.email)
