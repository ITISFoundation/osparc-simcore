# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_payments.core.settings import ApplicationSettings


def test_valid_web_application_settings(app_environment: EnvVarsDict):
    settings = ApplicationSettings()  # type: ignore
    assert settings

    assert settings == ApplicationSettings.create_from_envs()

    assert app_environment["PAYMENTS_LOGLEVEL"] == settings.LOG_LEVEL
