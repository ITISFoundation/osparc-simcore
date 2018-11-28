""" Basic configuration file for docker registry

"""
from os import environ as env

import trafaret as T

# TODO: adapt all data below!
CONFIG_SCHEMA = T.Dict({
    "user": T.String(),
    "password": T.String(),
    "registry": T.String()
})


class Config():
    # TODO: uniform config classes . see server.config file
    def __init__(self):
        REGISTRY = env.get("DOCKER_REGISTRY_HOST", "masu.speag.com")
        USER = env.get("DOCKER_REGISTRY_USER", "z43")
        PWD = env.get("DOCKER_REGISTRY_PWD", "z43")

        self._registry = REGISTRY
        self._user = USER
        self._pwd = PWD

    @property
    def registry(self):
        return self._registry + "/v2"

    @property
    def registry_name(self):
        return self._registry

    @property
    def user(self):
        return self._user

    @property
    def pwd(self):
        return self._pwd
