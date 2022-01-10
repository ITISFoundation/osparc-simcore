#
# SEE https://docs.locust.io/en/stable/quickstart.html
#

import logging
import os
from functools import cached_property
from re import L
from typing import NamedTuple

import locust_plugins
from dotenv import load_dotenv
from locust import task
from locust.contrib.fasthttp import FastHttpUser

logging.basicConfig(level=logging.INFO)


load_dotenv()  # take environment variables from .env

_UNDEFINED = "undefined"


class LocustAuth(NamedTuple):
    username: str = os.environ.get("USER_NAME", _UNDEFINED)
    password: str = os.environ.get("PASSWORD", _UNDEFINED)

    @cached_property
    def defined(self) -> bool:
        return _UNDEFINED not in (self.username, self.password)


class WebApiUser(FastHttpUser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth = LocustAuth()

    @task(10)
    def get_root(self):
        self.client.get("", auth=AUTH)

    @task(10)
    def get_root_slash(self):
        self.client.get("/", auth=AUTH)

    @task(1)
    def get_health(self):
        self.client.get("/v0/health", auth=AUTH)

    def on_start(self):
        print("Created locust user")

    def on_stop(self):
        print("Stopping locust user")
