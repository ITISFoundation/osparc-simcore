#
# SEE https://docs.locust.io/en/stable/quickstart.html
#

import logging
from pathlib import Path

import locust_plugins
from locust import task
from locust.contrib.fasthttp import FastHttpUser
from pydantic import Field
from pydantic_settings import BaseSettings

logging.basicConfig(level=logging.INFO)


# NOTE: 'import locust_plugins' is necessary to use --check-fail-ratio
# this assert is added to avoid that pycln pre-commit hook does not
# remove the import (the tool assumes the import is not necessary)
assert locust_plugins  # nosec


class LocustAuth(BaseSettings):
    SC_USER_NAME: str = Field(default=..., examples=["<your username>"])
    SC_PASSWORD: str = Field(default=..., examples=["<your password>"])


class WebApiUser(FastHttpUser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _auth = LocustAuth()
        self.auth = (
            _auth.SC_USER_NAME,
            _auth.SC_PASSWORD,
        )

    @task(10)
    def get_root(self):
        self.client.get("", auth=self.auth)

    @task(10)
    def get_root_slash(self):
        self.client.get("/", auth=self.auth)

    @task(1)
    def get_health(self):
        self.client.get("/v0/health", auth=self.auth)

    def on_start(self):  # pylint: disable=no-self-use
        print("Created locust user")

    def on_stop(self):  # pylint: disable=no-self-use
        print("Stopping locust user")


if __name__ == "__main__":
    from locust_settings import LocustSettings, dump_dotenv

    class LoadTestSettings(LocustAuth, LocustSettings):
        pass

    dump_dotenv(
        LoadTestSettings(
            LOCUST_LOCUSTFILE=Path(__file__).relative_to(Path(__file__).parent.parent)
        )
    )
