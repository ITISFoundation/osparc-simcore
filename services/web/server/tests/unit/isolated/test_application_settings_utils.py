from typing import Callable

from pytest_simcore.helpers.utils_dict import ConfigDict
from simcore_service_webserver.application_settings import ApplicationSettings
from simcore_service_webserver.application_settings_utils import (
    convert_to_app_config,
    convert_to_environ_vars,
)


def test_settings_infered_from_config(
    default_app_cfg: ConfigDict, monkeypatch_setenv_from_app_config: Callable
):
    envs = monkeypatch_setenv_from_app_config(default_app_cfg)
    assert envs == convert_to_environ_vars(default_app_cfg)

    settings = ApplicationSettings.create_from_envs()

    print("settings=\n", settings.json(indent=1, sort_keys=True))

    infered_config = convert_to_app_config(settings)
    assert default_app_cfg == infered_config
