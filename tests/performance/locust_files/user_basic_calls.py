#
# SEE https://docs.locust.io/en/stable/quickstart.html
#

import logging
import time

import faker
from locust import task
from locust.contrib.fasthttp import FastHttpUser

logging.basicConfig(level=logging.INFO)

fake = faker.Faker()


class WebApiUser(FastHttpUser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.timeout = 20000
        self.email = fake.email()
        self.password = "my_secret"

    def timed_get_request(self, route, resource_label):
        start = round(time.time() * 1000)
        with self.client.get(route, catch_response=True) as response:
            response_time = round(time.time() * 1000) - start
            print(
                "get",
                resource_label,
                "status",
                response.status_code,
                "timing",
                response_time,
            )
            if response.status_code == 200:
                response.success()
            else:
                response.failure("Got wrong response" + str(response.status_code))
            if response_time > self.timeout:
                print("TOO SLOW " + str(response_time / 1000) + " seconds")
            return response

    @task
    def get_studies(self):
        route = "v0/projects?type=user&offset=0&limit=20"
        resource_label = "studies"
        self.timed_get_request(route, resource_label)

    @task
    def get_templates(self):
        route = "v0/projects?type=template&offset=0&limit=20"
        resource_label = "templates"
        self.timed_get_request(route, resource_label)

    @task
    def get_services(self):
        route = "v0/catalog/services"
        resource_label = "services"
        self.timed_get_request(route, resource_label)

    def register(self, username, password):
        print("Register User ", username)
        self.client.post(
            "v0/auth/register",
            json={
                "email": username,
                "password": password,
                "confirm": password,
            },
        )

    def login(self, username, password):
        print("Log in User ", username)
        self.client.post(
            "v0/auth/login",
            json={
                "email": username,
                "password": password,
            },
        )

    def logout(self, username):
        print("Log out User ", username)
        self.client.post("v0/auth/logout", catch_response=True)

    def on_start(self):
        self.register(self.email, self.password)
        self.login(self.email, self.password)

    def on_stop(self):
        self.logout(self.email)
