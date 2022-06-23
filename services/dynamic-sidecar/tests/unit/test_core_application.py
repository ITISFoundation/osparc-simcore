# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import inspect

from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_sidecar.core.application import AppState, create_app
from simcore_service_dynamic_sidecar.core.settings import DynamicSidecarSettings


def test_create_app(mock_environment_with_envdevel: EnvVarsDict):
    app = create_app()
    assert isinstance(app.state.settings, DynamicSidecarSettings)

    # ensure exposed properties are init after creation
    app_state = AppState(app)
    properties = inspect.getmembers(AppState, lambda o: isinstance(o, property))

    for prop_name, _ in properties:
        assert getattr(app_state, prop_name) == getattr(app.state, prop_name)
