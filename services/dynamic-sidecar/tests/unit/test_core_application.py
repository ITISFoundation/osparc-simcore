# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import inspect
from typing import Union, get_args, get_origin

from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_sidecar.core.application import AppState, create_app
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.models.shared_store import SharedStore

pytest_simcore_core_services_selection = [
    "postgres",
]

pytest_simcore_ops_services_selection = [
    "adminer",
]


def test_create_app(mock_environment_with_envdevel: EnvVarsDict):
    app = create_app()
    assert isinstance(app.state.settings, ApplicationSettings)


def test_class_appstate_decorator_class(mock_environment_with_envdevel: EnvVarsDict):
    app = create_app()
    app.state.shared_store = SharedStore()  # emulate on_startup event
    app_state = AppState(app)

    # ensure exposed properties are init after creation
    properties = inspect.getmembers(
        AppState,
        lambda o: isinstance(o, property) and o.fget.__name__ in AppState._STATES,
    )
    for prop_name, prop in properties:
        # checks GETTERS

        # app.state.prop_name -> ReturnType annotation?
        value = getattr(app_state, prop_name)

        return_annotation = inspect.signature(prop.fget).return_annotation
        if get_origin(return_annotation) is Union:
            return_annotation = tuple(
                t for t in get_args(return_annotation) if inspect.isclass(t)
            )

        assert isinstance(value, return_annotation)

        # app.state.prop_name == app_state.prop_name
        assert getattr(app.state, prop_name) == value
