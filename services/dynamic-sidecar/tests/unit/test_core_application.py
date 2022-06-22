# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_sidecar.core.application import create_app
from simcore_service_dynamic_sidecar.core.settings import DynamicSidecarSettings


def test_init_appication(mock_environment_with_envdevel: EnvVarsDict):

    app = create_app()
    assert isinstance(app.state.settings, DynamicSidecarSettings)
