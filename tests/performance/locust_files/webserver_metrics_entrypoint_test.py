#
# SEE https://docs.locust.io/en/stable/quickstart.html
#

import logging
import os
from json.decoder import JSONDecodeError
from typing import Any, Dict
from uuid import uuid4

import faker
from dotenv import load_dotenv

from locust import task
from locust.contrib.fasthttp import FastHttpUser

logging.basicConfig(level=logging.INFO)

fake = faker.Faker()

load_dotenv()  # take environment variables from .env

_TEMPLATE_PROJECT_ID = "c2032f18-ddb9-11eb-a06f-02420a0000c1"


class WebApiUser(FastHttpUser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.email = fake.email()
        self.count = 0

    @task(weight=1)
    def health_check(self):
        self.client.get("/v0/health")

    @task(weight=1)
    def get_metrics(self):
        self.client.get(
            "/metrics",
        )

    @task(weight=5)
    def create_project_from_template_open_and_close(self):
        self.count += 1

        # WARNING: this template needs to be created and shared with everybody
        project: Dict[str, Any] = {}
        with self.client.post(
            f"/v0/projects?from_template={_TEMPLATE_PROJECT_ID}",
            json={
                "name": f"TEST #{self.count}",
                "description": f"{__name__}-{self.email}",
                "prjOwner": self.email,
            },
            catch_response=True,
            name="/projects/FROM_TEMPLATE",
        ) as response:
            try:
                project = response.json()["data"]
            except (JSONDecodeError, KeyError):
                response.failure("invalid response after creating project")

        if not project:
            raise ValueError("project not found???")
        # open the project
        client_session_id = str(uuid4())
        with self.client.post(
            f"/v0/projects/{project['uuid']}:open",
            json=client_session_id,
            catch_response=True,
            name="/projects/OPEN",
        ) as response:
            try:
                project = response.json()["data"]
            except (JSONDecodeError, KeyError):
                response.failure("invalid response after opening project")

        # close the project
        self.client.post(
            f"/v0/projects/{project['uuid']}:close",
            json=client_session_id,
            catch_response=True,
            name="/projects/CLOSE",
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
