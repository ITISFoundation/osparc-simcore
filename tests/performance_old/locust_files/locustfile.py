#
# SEE https://docs.locust.io/en/stable/quickstart.html
#

import logging
from uuid import UUID

import faker
from locust import HttpUser, between, task
from pydantic import Field
from pydantic_settings import BaseSettings

logging.basicConfig(level=logging.INFO)

fake = faker.Faker()


class TemplateSettings(BaseSettings):
    TEMPLATE_PROJECT_ID: UUID = Field(
        default=..., examples=["8de6acbe-ee58-46cd-8858-b925b96bc698"]
    )


class WebApiUser(HttpUser):
    wait_time = between(
        1, 2.5
    )  #  simulated users wait between 1 and 2.5 seconds after each task (see below) is executed.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.template_id = TemplateSettings().TEMPLATE_PROJECT_ID
        self.email = fake.email()
        self.count = 0

    @task
    def health_check(self):
        self.client.get("/v0/health")

    @task(weight=5)
    def create_project_from_template(self):
        self.count += 1

        # WARNING: this template needs to be created and shared with everybody
        self.client.post(
            f"/v0/projects?from_study={self.template_id}",
            json={
                "uuid": "",
                "name": f"TEST #{self.count}",
                "description": f"{__name__}-{self.email}",
                "prjOwner": self.email,
                "accessRights": {},
                "creationDate": "2021-04-28T14:46:53.674Z",
                "lastChangeDate": "2021-04-28T14:46:53.674Z",
                "thumbnail": "",
                "workbench": {},
            },
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
