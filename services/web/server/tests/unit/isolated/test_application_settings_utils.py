from typing import Callable

import pytest
from pytest_simcore.helpers.dict_tools import ConfigDict
from simcore_service_webserver.application_settings import ApplicationSettings
from simcore_service_webserver.application_settings_utils import (
    convert_to_app_config,
    convert_to_environ_vars,
)


@pytest.mark.skip(reason="UNDER DEV")
def test_settings_infered_from_default_tests_config(
    default_app_cfg: ConfigDict, monkeypatch_setenv_from_app_config: Callable
):
    # TODO: use app_config_for_production_legacy
    envs = monkeypatch_setenv_from_app_config(default_app_cfg)
    assert envs == convert_to_environ_vars(default_app_cfg)

    settings = ApplicationSettings.create_from_envs()

    print("settings=\n", settings.model_dump_json(indent=1))

    infered_config = convert_to_app_config(settings)

    assert default_app_cfg == infered_config
    assert set(default_app_cfg.keys()) == set(infered_config.keys())
