from typing import cast

from aws_library.ssm import SimcoreSSMAPI
from aws_library.ssm import configure_ssm_client as _configure_ssm_client
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from settings_library.ssm import SSMSettings

from ..core.errors import ConfigurationError


def configure_ssm_client(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: SSMSettings | None,
) -> None:
    _configure_ssm_client(
        app_lifespan,
        settings=settings,
        client_name="autoscaling",
    )


def get_ssm_client(app: FastAPI) -> SimcoreSSMAPI:
    if not hasattr(app.state, "ssm_client") or not app.state.ssm_client:
        raise ConfigurationError(msg="SSM client is not available. Please check the configuration.")
    return cast(SimcoreSSMAPI, app.state.ssm_client)
