import os

from locust import HttpLocust, TaskSet, between, task
import uuid as uuidlib


class UserBehaviour(TaskSet):
    def on_start(self):
        """ on_start is called when a Locust start before any task is scheduled """
        self._login()
        self._client_session_id = uuidlib.uuid4()  # pylint: disable=attribute-defined-outside-init

    def on_stop(self):
        """ on_stop is called when the TaskSet is stopping """
        self._logout()

    def _login(self):
        self.client.post(
            "/v0/auth/login",
            json={
                "email": os.environ.get("TEST_USER", "test@test.com"),
                "password": os.environ.get("TEST_PASSWORD", "test"),
            },
        )

    def _logout(self):
        self.client.post(
            "/v0/auth/logout", json={"client_session_id": str(self._client_session_id) }
        )

    @property
    def short_id(self) -> str:
        return str(self._client_session_id)[:4]

    @task(1)
    def get_me(self):
        print(f"{self.short_id} get_me")
        self.client.get("/v0/me")

    @task(2)
    def list_projects(self):
        print(f"{self.short_id} list_projects")
        self.client.get("/v0/projects")


class WebsiteUser(HttpLocust):
    task_set = UserBehaviour
    wait_time = between(5, 9)
