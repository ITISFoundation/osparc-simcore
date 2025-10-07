from collections.abc import Callable

from simcore_service_webserver.application_settings import ApplicationSettings
from simcore_service_webserver.application_settings_utils import (
    AppConfigDict,
    convert_to_app_config,
    convert_to_environ_vars,
)


def test_settings_infered_from_default_tests_config(
    default_app_cfg: AppConfigDict, monkeypatch_setenv_from_app_config: Callable
):
    envs = monkeypatch_setenv_from_app_config(default_app_cfg)
    assert envs == {
        k: f"{v}" for k, v in convert_to_environ_vars(default_app_cfg).items()
    }

    settings = ApplicationSettings.create_from_envs(WEBSERVER_RPC_NAMESPACE=None)

    assert convert_to_app_config(settings)
