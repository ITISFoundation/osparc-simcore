from typing import cast

from aws_library.ec2 import SimcoreEC2API
from aws_library.ec2 import configure_ec2_client as _configure_ec2_client
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from settings_library.ec2 import EC2Settings

from ..core.errors import ConfigurationError
from .instrumentation import has_instrumentation, instrument_ec2_client_methods


async def _create_ec2_client(app: FastAPI, settings: EC2Settings) -> SimcoreEC2API:
    ec2_client = await SimcoreEC2API.create(settings)
    if not has_instrumentation(app):
        return ec2_client
    return instrument_ec2_client_methods(app, ec2_client)


def configure_ec2_client(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: EC2Settings | None,
) -> None:
    _configure_ec2_client(
        app_lifespan,
        settings=settings,
        client_name="autoscaling",
        client_factory=_create_ec2_client,
    )


def get_ec2_client(app: FastAPI) -> SimcoreEC2API:
    if not hasattr(app.state, "ec2_client") or not app.state.ec2_client:
        raise ConfigurationError(msg="EC2 client is not available. Please check the configuration.")
    return cast(SimcoreEC2API, app.state.ec2_client)
