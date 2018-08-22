""" Basic configuration file for docker registry

"""
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
        self._registry = "masu.speag.com"
        self._user = "z43"
        self._pwd = "z43"

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
