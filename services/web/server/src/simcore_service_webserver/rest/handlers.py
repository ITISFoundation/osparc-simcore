"""This is a generated stub of handlers to be connected to the paths defined in the API

"""
import logging

from aiohttp import web_exceptions

from .generated_code.models.health_check import HealthCheck
from .generated_code.models.health_check_enveloped import HealthCheckEnveloped


_LOGGER = logging.getLogger(__name__)

async def check_health(request):
    # TODO: unify location of service info. setup.py should take if from there?
    info = HealthCheck(
        name = "simcore-service-webserver",
        status = "running",
        version = "0.0",
        api_version = "1.0")

    return HealthCheckEnveloped(data=info, status=200)

async def get_me(request):
    pass

async def register_user(request):
    pass

async def confirm_token(request):
    pass

async def login(request):
    pass

async def logout(request):
    pass
