import os
from io import StringIO

from _pytest.monkeypatch import MonkeyPatch
from dotenv import dotenv_values

from .typing_env import EnvVarsDict


def load_dotenv(envfile_text: str) -> EnvVarsDict:
    return {k: v or "" for k, v in dotenv_values(stream=StringIO(envfile_text)).items()}


def setenvs_from_dict(monkeypatch: MonkeyPatch, envs: EnvVarsDict):
    for key, value in envs.items():
        assert value is not None  # None keys cannot be is defined w/o value
        monkeypatch.setenv(key, str(value))
    return envs


def setenvs_as_envfile(monkeypatch: MonkeyPatch, envfile_text: str) -> EnvVarsDict:
    envs = load_dotenv(envfile_text)
    setenvs_from_dict(monkeypatch, envs)

    assert all(env in os.environ for env in envs)
    return envs


def delenvs_as_envfile(
    monkeypatch: MonkeyPatch, envfile_text: str, raising: bool
) -> EnvVarsDict:
    envs = load_dotenv(envfile_text)
    for key in envs.keys():
        monkeypatch.delenv(key, raising=raising)

    assert all(env not in os.environ for env in envs)
    return envs
