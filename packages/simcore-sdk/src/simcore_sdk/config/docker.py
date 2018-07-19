""" Basic configuration file for docker registry

"""

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
