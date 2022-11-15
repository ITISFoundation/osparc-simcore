from fastapi import FastAPI

from . import utils_aws, utils_docker
from .core.settings import ApplicationSettings


async def check_dynamic_resources(app: FastAPI) -> None:
    app_settings: ApplicationSettings = app.state.settings

    # NOTE: user_data is a script that gets launched when a new node is created
    assert app_settings.AUTOSCALING_AWS  # nosec
    user_data = utils_aws.compose_user_data(app_settings.AUTOSCALING_AWS)
    need_resources = await utils_docker.need_resources()
    import pdb

    pdb.set_trace()
