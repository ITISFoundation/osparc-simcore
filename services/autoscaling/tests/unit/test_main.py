# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_autoscaling.main import the_app, the_settings


def test_main_app(app_environment: EnvVarsDict):
    assert the_app.state.settings == the_settings
