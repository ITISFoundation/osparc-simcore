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


def test_AppState_decorator_class(mock_environment_with_envdevel: EnvVarsDict):
    app = create_app()
    app_state = AppState(app)

    # ensure exposed properties are init after creation
    properties = inspect.getmembers(AppState, lambda o: isinstance(o, property))
    for prop_name, prop in properties:
        # app.state.prop_name -> ReturnType annotation?
        value = getattr(app_state, prop_name)
        assert isinstance(value, inspect.signature(prop.fget).return_annotation)

        # app.state.prop_name == app_state.prop_name
        assert getattr(app.state, prop_name) == value
