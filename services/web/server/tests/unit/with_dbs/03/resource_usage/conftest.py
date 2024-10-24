# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict

API_VERSION = "v0"
RESOURCE_NAME = "projects"
API_PREFIX = "/" + API_VERSION


DEFAULT_GARBAGE_COLLECTOR_INTERVAL_SECONDS: int = 3
DEFAULT_GARBAGE_COLLECTOR_DELETION_TIMEOUT_SECONDS: int = 3


def app_environment(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    # print( ApplicationSettings.create_from_envs().model_dump_json((indent=1 )

    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_DB_LISTENER": "0",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_ANNOUNCEMENTS": "1",
        },
    )
