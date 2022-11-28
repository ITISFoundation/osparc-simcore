"""
.env (dotenv) files (or envfile)
"""

import os
from copy import deepcopy
from io import StringIO
from pathlib import Path
from typing import Union

import dotenv
from pytest import MonkeyPatch

from .typing_env import EnvVarsDict


#
# monkeypatch using dict
#
def setenvs_from_dict(monkeypatch: MonkeyPatch, envs: EnvVarsDict) -> EnvVarsDict:
    for key, value in envs.items():
        assert value is not None  # None keys cannot be is defined w/o value
        monkeypatch.setenv(key, str(value))
    return deepcopy(envs)


def load_dotenv(envfile_content_or_path: Union[Path, str], **options) -> EnvVarsDict:
    """Convenient wrapper around dotenv.dotenv_values"""
    kwargs = options.copy()
    if isinstance(envfile_content_or_path, Path):
        # path
        kwargs["dotenv_path"] = envfile_content_or_path
    else:
        assert isinstance(envfile_content_or_path, str)
        # content
        kwargs["stream"] = StringIO(envfile_content_or_path)

    return {k: v or "" for k, v in dotenv.dotenv_values(**kwargs).items()}


#
# monkeypath using envfiles ('.env' and also denoted as dotfiles)
#


def setenvs_from_envfile(
    monkeypatch: MonkeyPatch, content_or_path: str, **dotenv_kwags
) -> EnvVarsDict:
    """Batch monkeypatch.setenv(...) on all env vars in an envfile"""
    envs = load_dotenv(content_or_path, **dotenv_kwags)
    setenvs_from_dict(monkeypatch, envs)

    assert all(env in os.environ for env in envs)
    return envs


def delenvs_from_envfile(
    monkeypatch: MonkeyPatch, content_or_path: str, raising: bool, **dotenv_kwags
) -> EnvVarsDict:
    """Batch monkeypatch.delenv(...) on all env vars in an envfile"""
    envs = load_dotenv(content_or_path, **dotenv_kwags)
    for key in envs.keys():
        monkeypatch.delenv(key, raising=raising)

    assert all(env not in os.environ for env in envs)
    return envs
