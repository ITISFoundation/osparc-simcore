# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import inspect
from collections.abc import AsyncIterator
from typing import Union, get_args, get_origin

from fastapi import FastAPI
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.tracing import TracingConfig
from simcore_service_dynamic_sidecar._meta import APP_NAME
from simcore_service_dynamic_sidecar.core.application import (
    AppState,
    create_app,
    create_app_lifespan,
    create_base_app,
)
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.models.shared_store import SharedStore
from simcore_service_dynamic_sidecar.modules.mounted_fs import MountedVolumes


def test_create_app(mock_environment_with_envdevel: EnvVarsDict):
    app = create_app()
    assert isinstance(app.state.settings, ApplicationSettings)


async def test_create_base_app_with_explicit_lifespan_manager(
    mock_environment_with_envdevel: EnvVarsDict,
):
    app_settings = ApplicationSettings.create_from_envs()
    tracing_config = TracingConfig.create(
        service_name=APP_NAME,
        tracing_settings=app_settings.DYNAMIC_SIDECAR_TRACING,
    )
    lifecycle_events: list[str] = []

    async def _probe_lifespan(_: FastAPI) -> AsyncIterator[None]:
        lifecycle_events.append("startup")
        try:
            yield
        finally:
            lifecycle_events.append("shutdown")

    with create_app_lifespan(app_settings, tracing_config) as app_lifespan:
        app = create_base_app(
            app_lifespan,
            app_settings=app_settings,
            tracing_config=tracing_config,
        )
        app_lifespan.add(_probe_lifespan)

    async with app_lifespan(app):
        assert lifecycle_events == ["startup"]

    assert lifecycle_events == ["startup", "shutdown"]


def test_class_appstate_decorator_class(mock_environment_with_envdevel: EnvVarsDict):
    app = create_app()
    settings: ApplicationSettings = app.state.settings
    app.state.mounted_volumes = MountedVolumes(
        service_run_id=settings.DY_SIDECAR_RUN_ID,
        node_id=settings.DY_SIDECAR_NODE_ID,
        inputs_path=settings.DY_SIDECAR_PATH_INPUTS,
        outputs_path=settings.DY_SIDECAR_PATH_OUTPUTS,
        user_preferences_path=settings.DY_SIDECAR_USER_PREFERENCES_PATH,
        state_paths=settings.DY_SIDECAR_STATE_PATHS,
        state_exclude=settings.DY_SIDECAR_STATE_EXCLUDE,
        compose_namespace=settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE,
        dy_volumes=settings.DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR,
    )
    app.state.shared_store = SharedStore()  # emulate on_startup event
    app_state = AppState(app)

    # ensure exposed properties are init after creation
    properties = inspect.getmembers(
        AppState,
        lambda o: isinstance(o, property) and o.fget.__name__ in AppState._STATES,  # noqa: SLF001
    )
    for prop_name, prop in properties:
        # checks GETTERS

        # app.state.prop_name -> ReturnType annotation?
        value = getattr(app_state, prop_name)

        return_annotation = inspect.signature(prop.fget).return_annotation
        if get_origin(return_annotation) is Union:
            return_annotation = tuple(t for t in get_args(return_annotation) if inspect.isclass(t))

        assert isinstance(value, return_annotation)

        # app.state.prop_name == app_state.prop_name
        assert getattr(app.state, prop_name) == value
