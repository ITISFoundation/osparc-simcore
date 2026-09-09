# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.tracing import TracingConfig
from simcore_service_catalog._meta import APP_NAME
from simcore_service_catalog.core.application import _configure_plugins
from simcore_service_catalog.core.settings import ApplicationSettings


def test_rpc_api_is_registered_after_director(app_environment: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    app = FastAPI()
    app.state.settings = settings
    app_lifespan = LifespanManager()

    _configure_plugins(
        app,
        app_lifespan,
        settings,
        TracingConfig.create(service_name=APP_NAME, tracing_settings=None),
    )

    names = [getattr(fn, "__name__", "") for fn in app_lifespan.lifespans]

    assert "director_lifespan" in names
    assert "rpc_api_lifespan" in names
    assert names.index("director_lifespan") < names.index("rpc_api_lifespan"), (
        "RPC inbound adapter must be registered AFTER director so it only "
        "starts consuming once app.state.director_api exists (see issue #9390)"
    )
