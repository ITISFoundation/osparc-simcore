#
# SEE https://docs.locust.io/en/stable/quickstart.html
#

import logging
import os
from typing import NamedTuple

import locust_plugins # necessary to use --check-fail-ratio 
from dotenv import load_dotenv
from locust import task
from locust.contrib.fasthttp import FastHttpUser

logging.basicConfig(level=logging.INFO)


load_dotenv()  # take environment variables from .env

_UNDEFINED = "undefined"


class LocustAuth(NamedTuple):
    username: str = os.environ.get("SC_USER_NAME", _UNDEFINED)
    password: str = os.environ.get("SC_PASSWORD", _UNDEFINED)

    def defined(self) -> bool:
        return _UNDEFINED not in (self.username, self.password)


class WebApiUser(FastHttpUser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth = LocustAuth()
        if not self.auth.defined():
            self.auth = None

    @task(10)
    def get_root(self):
        self.client.get("", auth=self.auth)

    @task(10)
    def get_root_slash(self):
        self.client.get("/", auth=self.auth)

    @task(1)
    def get_health(self):
        self.client.get("/v0/health", auth=self.auth)

    def on_start(self):
        print("Created locust user")

    def on_stop(self):
        print("Stopping locust user")
