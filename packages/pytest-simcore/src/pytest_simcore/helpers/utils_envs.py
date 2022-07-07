import os
from io import StringIO
from pathlib import Path
from typing import Union

import dotenv
from pytest import MonkeyPatch

from .typing_env import EnvVarsDict


#
# monkeypatch using dict
#
def setenvs_from_dict(monkeypatch: MonkeyPatch, envs: EnvVarsDict):
    for key, value in envs.items():
        assert value is not None  # None keys cannot be is defined w/o value
        monkeypatch.setenv(key, str(value))
    return envs


#
# .env (dotenv) files (or envfile)
#


def load_dotenv(envfile: Union[Path, str], **options) -> EnvVarsDict:
    """Convenient wrapper around dotenv.dotenv_values"""
    kwargs = options.copy()
    if isinstance(envfile, Path):
        # path
        kwargs["dotenv_path"] = envfile
    else:
        # content
        kwargs["stream"] = StringIO(envfile)

    return {k: v or "" for k, v in dotenv.dotenv_values(**kwargs).items()}


#
# monkeypath using envfiles
#


def setenvs_as_envfile(
    monkeypatch: MonkeyPatch, envfile_text: str, **dotenv_kwags
) -> EnvVarsDict:
    envs = load_dotenv(envfile_text, **dotenv_kwags)
    setenvs_from_dict(monkeypatch, envs)

    assert all(env in os.environ for env in envs)
    return envs


def delenvs_as_envfile(
    monkeypatch: MonkeyPatch, envfile_text: str, raising: bool, **dotenv_kwags
) -> EnvVarsDict:
    envs = load_dotenv(envfile_text, **dotenv_kwags)
    for key in envs.keys():
        monkeypatch.delenv(key, raising=raising)

    assert all(env not in os.environ for env in envs)
    return envs
