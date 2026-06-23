from typing import cast

from aws_library.ec2 import SimcoreEC2API
from aws_library.ec2 import configure_ec2_client as _configure_ec2_client
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from settings_library.ec2 import EC2Settings

from ..core.errors import ConfigurationError


def configure_ec2_client(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: EC2Settings | None,
) -> None:
    _configure_ec2_client(
        app_lifespan,
        settings=settings,
        client_name="clusters_keeper",
    )


def get_ec2_client(app: FastAPI) -> SimcoreEC2API:
    if not app.state.ec2_client:
        raise ConfigurationError(msg="EC2 client is not available. Please check the configuration.")
    return cast(SimcoreEC2API, app.state.ec2_client)
