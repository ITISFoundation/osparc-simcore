import os
from io import StringIO

from _pytest.monkeypatch import MonkeyPatch
from dotenv import dotenv_values

from .typing_env import EnvVarsDict


def setenvs_as_envfile(monkeypatch: MonkeyPatch, envfile_text: str) -> EnvVarsDict:
    envs = dotenv_values(stream=StringIO(envfile_text))
    for key, value in envs.items():
        monkeypatch.setenv(key, str(value))

    assert all(env in os.environ for env in envs)
    return envs


def delenvs_as_envfile(
    monkeypatch: MonkeyPatch, envfile_text: str, raising: bool
) -> EnvVarsDict:
    envs = dotenv_values(stream=StringIO(envfile_text))
    for key in envs.keys():
        monkeypatch.delenv(key, raising=raising)

    assert all(env not in os.environ for env in envs)
    return envs
